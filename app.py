import os
import sqlite3
import time
import eventlet

from flask import Flask, render_template, redirect, url_for, request
from flask_socketio import SocketIO, emit
import minimalmodbus

# ----------------------------
# Configuratie
# ----------------------------
RS485_PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
COIL_ADDRESS = 0
INPUT_REGISTER_ADDRESS = 0
DB_FILE = 'settings.db'

UNITS = [
    {'slave_id': 1,  'name': 'Relay Module 1',  'type': 'relay'},
    {'slave_id': 2,  'name': 'Relay Module 2',  'type': 'relay'},
    {'slave_id': 3,  'name': 'Relay Module 3',  'type': 'relay'},
    {'slave_id': 4,  'name': 'Relay Module 4',  'type': 'relay'},
    {'slave_id': 5,  'name': 'Analog Input 1',  'type': 'analog'},
    {'slave_id': 6,  'name': 'Analog Input 2',  'type': 'analog'},
    {'slave_id': 7,  'name': 'Analog Input 3',  'type': 'analog'},
    {'slave_id': 8,  'name': 'Analog Input 4',  'type': 'analog'},
    {'slave_id': 9,  'name': 'EX1608DD',        'type': 'relay'},
    {'slave_id': 10, 'name': 'EX04AIO',          'type': 'aio'},
]

# ----------------------------
# App & SocketIO setup
# ----------------------------
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

# ----------------------------
# Globals
# ----------------------------
clients = []
fallback_mode = False
log_messages = []
MAX_LOG_MESSAGES = 20
current_unit = 0

# ----------------------------
# Database helpers
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS calibration (
            unit_index INTEGER NOT NULL,
            channel    INTEGER NOT NULL,
            scale      REAL    NOT NULL,
            offset     REAL    NOT NULL,
            PRIMARY KEY(unit_index, channel)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_calibration(unit_index, channel):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT scale, offset FROM calibration WHERE unit_index=? AND channel=?',
              (unit_index, channel))
    row = c.fetchone(); conn.close()
    return {'scale': row[0], 'offset': row[1]} if row else {'scale': 1.0, 'offset': 0.0}

def set_calibration_db(unit_index, channel, scale, offset):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('''
        INSERT INTO calibration(unit_index, channel, scale, offset)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(unit_index, channel) DO UPDATE SET
            scale=excluded.scale,
            offset=excluded.offset
    ''', (unit_index, channel, scale, offset))
    conn.commit(); conn.close()

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('''
        INSERT INTO settings(key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value
    ''', (key, str(value)))
    conn.commit(); conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone(); conn.close()
    return row[0] if row else default

# ----------------------------
# Logging helper
# ----------------------------
def log(message):
    global log_messages
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {message}"
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG_MESSAGES:
        log_messages[:] = log_messages[-MAX_LOG_MESSAGES:]
    print(entry)

# ----------------------------
# Modbus init
# ----------------------------
def init_modbus():
    global fallback_mode, clients
    clients = []
    success = True
    for u in UNITS:
        client = minimalmodbus.Instrument(RS485_PORT, u['slave_id'], mode='rtu')
        client.serial.baudrate  = BAUDRATE
        client.serial.parity    = minimalmodbus.serial.PARITY_EVEN
        client.serial.stopbits  = 1
        client.serial.bytesize  = 8
        client.serial.timeout   = 3
        clients.append(client)
    for i, u in enumerate(UNITS):
        try:
            if u['type'] == 'relay':
                clients[i].read_bit(COIL_ADDRESS, functioncode=1)
            elif u['type'] == 'analog':
                clients[i].read_register(INPUT_REGISTER_ADDRESS, functioncode=4)
            elif u['type'] == 'aio':
                clients[i].read_register(0, functioncode=3)
            log(f"Modbus OK voor {u['name']} (ID {u['slave_id']})")
        except Exception as e:
            log(f"Modbus init fout voor {u['name']} (ID {u['slave_id']}): {e}")
            success = False
    fallback_mode = not success

# ----------------------------
# Relay helpers
# ----------------------------
def set_relay_state(state):
    if fallback_mode: log(f"[FALLBACK] Simuleer relay → {state}"); return
    try:
        clients[current_unit].write_bit(COIL_ADDRESS, state, functioncode=5)
        log(f"Relay gezet op {state}")
    except Exception as e:
        log(f"Fout set_relay_state: {e}")

def toggle_relay():
    if fallback_mode: log("[FALLBACK] Simuleer toggle"); return
    try:
        cur = clients[current_unit].read_bit(COIL_ADDRESS, functioncode=1)
        set_relay_state(not cur)
    except Exception as e:
        log(f"Fout toggle_relay: {e}")

def get_coil_status():
    if fallback_mode: return "Unknown"
    try:
        s = clients[current_unit].read_bit(COIL_ADDRESS, functioncode=1)
        return "ON" if s else "OFF"
    except Exception as e:
        log(f"Fout get_coil_status: {e}"); return "Err"

# ----------------------------
# Analog helpers
# ----------------------------
def get_analog_value():
    if fallback_mode: return "Unknown"
    try:
        return clients[current_unit].read_register(INPUT_REGISTER_ADDRESS, functioncode=4)
    except Exception as e:
        log(f"Fout get_analog_value: {e}"); return "Err"

# ----------------------------
# AIO helpers
# ----------------------------
def read_aio_input(i, ch):  return clients[i].read_register(ch, functioncode=4)
def read_aio_output(i, ch): return clients[i].read_register(ch, functioncode=3)
def set_aio_output(i, ch, raw):
    raw = max(0, min(4095, raw))
    clients[i].write_register(ch, raw, functioncode=6)
    log(f"EX04AIO ch{ch} OUTPUT → raw {raw}")

# ----------------------------
# Sensor monitor
# ----------------------------
def sensor_monitor():
    while True:
        if not fallback_mode:
            readings = []
            for i,u in enumerate(UNITS):
                if u['type']=='analog':
                    for ch in range(4):
                        try:
                            raw = clients[i].read_register(ch, functioncode=4)
                            cal = get_calibration(i, ch)
                            val = raw*cal['scale']+cal['offset']
                            readings.append({
                                'name':u['name'],'slave_id':u['slave_id'],
                                'channel':ch,'raw':raw,'value':round(val,2)
                            })
                        except: pass
            socketio.emit('sensor_update', readings, namespace='/sensors')
        eventlet.sleep(2)

# ----------------------------
# HTTP Routes
# ----------------------------
@app.route('/')
def index():
    return render_template('test_all_units.html',
        fallback_mode=fallback_mode,
        status=(get_coil_status() if UNITS[current_unit]['type']=='relay'
                else get_analog_value()),
        coil_number=COIL_ADDRESS,
        register_number=INPUT_REGISTER_ADDRESS,
        current_unit_index=current_unit,
        current_unit_name=UNITS[current_unit]['name'],
        unit_type=UNITS[current_unit]['type'],
        units=UNITS,
        log_messages=log_messages
    )

@app.route('/relays', methods=['GET','POST'])
def relays():
    global current_unit
    if request.method=='POST':
        unit_idx = int(request.form['unit_idx'])
        current_unit = unit_idx
        action = request.form['action']
        if action=='on':    set_relay_state(True)
        if action=='off':   set_relay_state(False)
        if action=='toggle':toggle_relay()
        time.sleep(0.1)
        return redirect(url_for('relays'))

    relay_status=[]
    prev = current_unit
    for i,u in enumerate(UNITS):
        if u['type']=='relay':
            current_unit=i
            state = get_coil_status()
            relay_status.append({
                'idx':i,'name':u['name'],'slave_id':u['slave_id'],'state':state
            })
    current_unit = prev
    return render_template('relays.html', relays=relay_status)

@app.route('/update_coil', methods=['POST'])
def update_coil():
    global COIL_ADDRESS
    COIL_ADDRESS = int(request.form['coil_number'])
    log(f"Set COIL_ADDRESS={COIL_ADDRESS}")
    return redirect(url_for('index'))

@app.route('/update_register', methods=['POST'])
def update_register():
    global INPUT_REGISTER_ADDRESS
    INPUT_REGISTER_ADDRESS = int(request.form['register_number'])
    log(f"Set REGISTER_ADDRESS={INPUT_REGISTER_ADDRESS}")
    return redirect(url_for('index'))

@app.route('/select_unit', methods=['POST'])
def select_unit():
    global current_unit
    current_unit = int(request.form['unit_index'])
    log(f"Select unit {UNITS[current_unit]['name']}")
    return redirect(url_for('index'))

@app.route('/sensors')
def sensors():
    return render_template('sensors.html', fallback_mode=fallback_mode)

@app.route('/aio', methods=['GET','POST'])
def aio():
    idx = next(i for i,u in enumerate(UNITS) if u['type']=='aio')
    readings = []
    # load saved setpoints
    for ch in range(4):
        saved = get_setting(f"aio_ch{ch}_setpoint", None)
        readings.append({'channel':ch,'saved_percent':saved})

    if request.method=='POST':
        ch = int(request.form['channel'])
        percent = float(request.form['percent_value'])
        mA = 4.0 + (percent/100.0)*16.0
        raw = int((mA/20.0)*4095)
        set_aio_output(idx,ch,raw)
        set_setting(f"aio_ch{ch}_setpoint", percent)
        time.sleep(0.1)
        for r in readings:
            if r['channel']==ch: r['saved_percent']=percent

    for r in readings:
        ch=r['channel']
        try:
            raw_in  = read_aio_input(idx,ch)
            raw_out = read_aio_output(idx,ch)
            cal     = get_calibration(idx,ch)
            phys_in = round(raw_in*cal['scale']+cal['offset'],2)
            phys_out= round((raw_out/4095.0)*20.0,2)
            percent_out = round((phys_out-4.0)/16.0*100.0,1) if phys_out>4.0 else None
        except Exception as e:
            log(f"AIO fout ch{ch}: {e}")
            raw_in=raw_out=phys_in=phys_out=percent_out=None
        r.update({'raw_in':raw_in,'phys_in':phys_in,
                  'raw_out':raw_out,'phys_out':phys_out,
                  'percent_out':percent_out})

    return render_template('aio.html', readings=readings,
                           unit=UNITS[idx], fallback_mode=fallback_mode)

@app.route('/calibrate')
def calibrate():
    return render_template('calibrate.html', units=UNITS)

# ----------------------------
# WebSocket Calibration
# ----------------------------
@socketio.on('connect', namespace='/cal')
def on_cal_connect():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT unit_index, channel, scale, offset FROM calibration')
    all_cal = {f"{r[0]}-{r[1]}":{'scale':r[2],'offset':r[3]} for r in c.fetchall()}
    conn.close(); emit('init_cal', all_cal)

# ----------------------------
# WebSocket Sensors
# ----------------------------
@socketio.on('connect', namespace='/sensors')
def on_sensors_connect():
    log("Client connected to /sensors")
    readings=[]
    for i,u in enumerate(UNITS):
        if u['type']=='analog':
            for ch in range(4):
                try:
                    raw=clients[i].read_register(ch, functioncode=4) if not fallback_mode else None
                    cal=get_calibration(i,ch)
                    val=raw*cal['scale']+cal['offset'] if raw is not None else None
                except: raw=val=None
                readings.append({
                    'name':u['name'],'slave_id':u['slave_id'],
                    'channel':ch,'raw':raw,
                    'value':round(val,2) if val is not None else None
                })
    emit('sensor_update', readings)

# ----------------------------
# Main
# ----------------------------
if __name__ == '__main__':
    init_db()
    init_modbus()
    socketio.start_background_task(sensor_monitor)
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, use_reloader=False)
