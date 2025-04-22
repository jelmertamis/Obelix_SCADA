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
DB_FILE = 'calibration.db'

UNITS = [
    {'slave_id': 1, 'name': 'Relay Module 1', 'type': 'relay'},
    {'slave_id': 2, 'name': 'Relay Module 2', 'type': 'relay'},
    {'slave_id': 3, 'name': 'Relay Module 3', 'type': 'relay'},
    {'slave_id': 4, 'name': 'Relay Module 4', 'type': 'relay'},
    {'slave_id': 5, 'name': 'Analog Input 1', 'type': 'analog'},
    {'slave_id': 6, 'name': 'Analog Input 2', 'type': 'analog'},
    {'slave_id': 7, 'name': 'Analog Input 3', 'type': 'analog'},
    {'slave_id': 8, 'name': 'Analog Input 4', 'type': 'analog'},
    {'slave_id': 9, 'name': 'EX1608DD',      'type': 'relay'},
    {'slave_id': 10, 'name': 'EX04AIO',      'type': 'aio'},
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
last_sensor_values = {}

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
            PRIMARY KEY (unit_index, channel)
        )
    ''')
    conn.commit()
    conn.close()

def get_calibration(unit_index, channel):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        'SELECT scale, offset FROM calibration WHERE unit_index=? AND channel=?',
        (unit_index, channel)
    )
    row = c.fetchone()
    conn.close()
    return {'scale': row[0], 'offset': row[1]} if row else {'scale': 1.0, 'offset': 0.0}

def set_calibration_db(unit_index, channel, scale, offset):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO calibration (unit_index, channel, scale, offset)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(unit_index, channel) DO UPDATE SET
            scale=excluded.scale,
            offset=excluded.offset
    ''', (unit_index, channel, scale, offset))
    conn.commit()
    conn.close()

def calculate_calibration(raw1, phys1, raw2, phys2):
    if raw1 == raw2:
        raise ValueError("Ruwe waarden moeten verschillend zijn")
    scale = (phys2 - phys1) / (raw2 - raw1)
    offset = phys1 - scale * raw1
    return scale, offset

# ----------------------------
# Logging helper
# ----------------------------
def log(message):
    global log_messages
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {message}"
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG_MESSAGES:
        log_messages = log_messages[-MAX_LOG_MESSAGES:]
    print(entry)

# ----------------------------
# Modbus init
# ----------------------------
def init_modbus():
    global fallback_mode
    try:
        for unit in UNITS:
            client = minimalmodbus.Instrument(RS485_PORT, unit['slave_id'], mode='rtu')
            client.serial.baudrate = BAUDRATE
            client.serial.parity   = minimalmodbus.serial.PARITY_EVEN
            client.serial.stopbits = 1
            client.serial.bytesize = 8
            client.serial.timeout  = 3
            clients.append(client)
        # test verbinding
        for i, unit in enumerate(UNITS):
            if unit['type'] in ('relay', 'aio'):
                clients[i].read_bit(COIL_ADDRESS, functioncode=1)
            else:
                clients[i].read_register(INPUT_REGISTER_ADDRESS, functioncode=4)
            log(f"Modbus OK voor {unit['name']} (ID {unit['slave_id']})")
        fallback_mode = False
    except Exception as e:
        log(f"Modbus init fout: {e} → fallback aan")
        fallback_mode = True

# ----------------------------
# Relay functies
# ----------------------------
def set_relay_state(state):
    if fallback_mode: 
        log(f"[FALLBACK] Simuleer relay → {state}")
        return
    try:
        clients[current_unit].write_bit(COIL_ADDRESS, state, functioncode=5)
        log(f"Relay {current_unit}:{COIL_ADDRESS} → {state}")
    except Exception as e:
        log(f"Fout set_relay_state: {e}")

def toggle_relay():
    if fallback_mode:
        log("[FALLBACK] Simuleer toggle relay")
        return
    try:
        cur = clients[current_unit].read_bit(COIL_ADDRESS, functioncode=1)
        set_relay_state(not cur)
    except Exception as e:
        log(f"Fout toggle_relay: {e}")

def get_coil_status():
    if fallback_mode:
        return "Unknown"
    try:
        s = clients[current_unit].read_bit(COIL_ADDRESS, functioncode=1)
        return "ON" if s else "OFF"
    except Exception as e:
        log(f"Fout get_coil_status: {e}")
        return "Err"

# ----------------------------
# Analog input
# ----------------------------
def get_analog_value():
    if fallback_mode:
        return "Unknown"
    try:
        return clients[current_unit].read_register(INPUT_REGISTER_ADDRESS, functioncode=4)
    except Exception as e:
        log(f"Fout get_analog_value: {e}")
        return "Err"

# ----------------------------
# EX04AIO helpers
# ----------------------------
def read_aio_input(unit_index, channel):
    return clients[unit_index].read_register(channel, functioncode=4)

def read_aio_output(unit_index, channel):
    return clients[unit_index].read_register(channel, functioncode=3)

def set_aio_output(unit_index, channel, raw_value):
    clients[unit_index].write_register(channel, raw_value, functioncode=6)
    log(f"EX04AIO {unit_index}:AOUT{channel} → raw {raw_value}")

# ----------------------------
# Sensor monitoring background task
# ----------------------------
def sensor_monitor():
    global last_sensor_values
    while True:
        if not fallback_mode:
            updates = []
            for i, unit in enumerate(UNITS):
                if unit['type'] == 'analog':
                    for ch in range(4):
                        try:
                            raw = clients[i].read_register(ch, functioncode=4)
                            cal = get_calibration(i, ch)
                            val = raw * cal['scale'] + cal['offset']
                            key = f"{i}-{ch}"
                            if key not in last_sensor_values or abs(last_sensor_values[key] - val) > 0.01:
                                last_sensor_values[key] = val
                                updates.append({
                                    'name': unit['name'],
                                    'slave_id': unit['slave_id'],
                                    'channel': ch,
                                    'raw': raw,
                                    'value': round(val, 2)
                                })
                        except Exception as e:
                            log(f"Fout sensor {unit['name']} ch{ch}: {e}")
            if updates:
                socketio.emit('sensor_update', updates, namespace='/sensors')
        eventlet.sleep(2)

# ----------------------------
# HTTP Routes
# ----------------------------
@app.route('/')
def index():
    if UNITS[current_unit]['type'] == 'relay':
        status = get_coil_status()
    else:
        status = get_analog_value()
    return render_template(
        'test_all_units.html',
        fallback_mode=fallback_mode,
        status=status,
        coil_number=COIL_ADDRESS,
        register_number=INPUT_REGISTER_ADDRESS,
        current_unit_index=current_unit,
        current_unit_name=UNITS[current_unit]['name'],
        unit_type=UNITS[current_unit]['type'],
        units=UNITS,
        log_messages=log_messages
    )

@app.route('/relay/<action>')
def relay_action(action):
    if UNITS[current_unit]['type'] != 'relay':
        log("Geen relais hier")
        return redirect(url_for('index'))
    if action == 'on':    set_relay_state(True)
    if action == 'off':   set_relay_state(False)
    if action == 'toggle': toggle_relay()
    time.sleep(1)
    return redirect(url_for('index'))

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

@app.route('/aio', methods=['GET', 'POST'])
def aio():
    unit_index = next(i for i, u in enumerate(UNITS) if u['type'] == 'aio')
    if request.method == 'POST':
        ch   = int(request.form['channel'])
        phys = float(request.form['phys_value'])
        cal  = get_calibration(unit_index, ch)
        raw  = int((phys - cal['offset']) / cal['scale'])
        set_aio_output(unit_index, ch, raw)
        time.sleep(0.1)

    readings = []
    for ch in range(4):
        raw_in  = read_aio_input(unit_index, ch) if not fallback_mode else None
        raw_out = read_aio_output(unit_index, ch) if not fallback_mode else None
        cal_in  = get_calibration(unit_index, ch)
        phys_in  = round(raw_in  * cal_in['scale']  + cal_in['offset'], 2) if raw_in is not None else None
        phys_out = round(raw_out * cal_in['scale']  + cal_in['offset'], 2) if raw_out is not None else None
        readings.append({
            'channel':  ch,
            'raw_in':   raw_in,
            'phys_in':  phys_in,
            'raw_out':  raw_out,
            'phys_out': phys_out
        })

    return render_template(
        'aio.html',
        unit=UNITS[unit_index],
        readings=readings,
        fallback_mode=fallback_mode
    )

@app.route('/calibrate')
def calibrate():
    return render_template('calibrate.html', units=UNITS)

# ----------------------------
# WebSocket voor kalibratie
# ----------------------------
@socketio.on('connect', namespace='/cal')
def on_connect():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT unit_index, channel, scale, offset FROM calibration')
    all_cal = {f"{r[0]}-{r[1]}": {'scale': r[2], 'offset': r[3]} for r in c.fetchall()}
    conn.close()
    emit('init_cal', all_cal)

@socketio.on('get_raw', namespace='/cal')
def on_get_raw(data):
    i, ch = data['unit_index'], data['channel']
    raw = None; calibrated = None
    try:
        raw = clients[i].read_register(ch, functioncode=4)
        cal = get_calibration(i, ch)
        calibrated = raw * cal['scale'] + cal['offset']
    except:
        pass
    emit('raw_value', {
        'unit': i,
        'channel': ch,
        'raw': raw,
        'calibrated': round(calibrated, 2) if calibrated is not None else None,
        'point': data.get('point')
    })

@socketio.on('set_cal_points', namespace='/cal')
def on_set_cal_points(data):
    try:
        unit, ch = data['unit'], data['channel']
        raw1, phys1 = data['raw1'], data['phys1']
        raw2, phys2 = data['raw2'], data['phys2']
        scale, offset = calculate_calibration(raw1, phys1, raw2, phys2)
        set_calibration_db(unit, ch, scale, offset)
        log(f"Kalibratie opgeslagen voor unit {unit}, kanaal {ch}: scale={scale}, offset={offset}")
        emit('cal_saved', {'unit': unit, 'channel': ch, 'scale': scale, 'offset': offset})
    except Exception as e:
        emit('cal_error', {'unit': data['unit'], 'channel': data['channel'], 'error': str(e)})

# ----------------------------
# WebSocket voor sensoren
# ----------------------------
@socketio.on('connect', namespace='/sensors')
def sensors_connect():
    log("Client connected to /sensors namespace")
    readings = []
    for i, unit in enumerate(UNITS):
        if unit['type'] == 'analog':
            for ch in range(4):
                raw = None; val = None
                try:
                    raw = clients[i].read_register(ch, functioncode=4)
                    cal = get_calibration(i, ch)
                    val = raw * cal['scale'] + cal['offset']
                except Exception as e:
                    log(f"Fout sensor {unit['name']} ch{ch}: {e}")
                readings.append({
                    'name': unit['name'],
                    'slave_id': unit['slave_id'],
                    'channel': ch,
                    'raw': raw,
                    'value': round(val, 2) if val is not None else None
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
