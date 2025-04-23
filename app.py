import os
import sqlite3
import time
import eventlet

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import minimalmodbus

# ----------------------------
# Configuration
# ----------------------------
RS485_PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
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
# Flask & SocketIO setup
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

# ----------------------------
# Database helpers
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # calibration table now includes phys_min and phys_max
    c.execute('''
      CREATE TABLE IF NOT EXISTS calibration (
        unit_index INTEGER NOT NULL,
        channel    INTEGER NOT NULL,
        scale      REAL    NOT NULL,
        offset     REAL    NOT NULL,
        phys_min   REAL    NOT NULL,
        phys_max   REAL    NOT NULL,
        PRIMARY KEY(unit_index, channel)
      )
    ''')
    # settings table for other persistence (e.g., AIO setpoints)
    c.execute('''
      CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''')
    conn.commit()
    conn.close()

def get_calibration(unit, channel):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      SELECT scale, offset, phys_min, phys_max
      FROM calibration
      WHERE unit_index=? AND channel=?
    ''', (unit, channel))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'scale':    row[0],
            'offset':   row[1],
            'phys_min': row[2],
            'phys_max': row[3]
        }
    # defaults: identity mapping
    return {'scale': 1.0, 'offset': 0.0, 'phys_min': 0.0, 'phys_max': 4095.0}

def save_calibration(unit, channel, scale, offset, phys_min, phys_max):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      INSERT INTO calibration(
        unit_index, channel, scale, offset, phys_min, phys_max
      ) VALUES (?,?,?,?,?,?)
      ON CONFLICT(unit_index,channel) DO UPDATE SET
        scale=excluded.scale,
        offset=excluded.offset,
        phys_min=excluded.phys_min,
        phys_max=excluded.phys_max
    ''', (unit, channel, scale, offset, phys_min, phys_max))
    conn.commit()
    conn.close()

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      INSERT INTO settings(key, value)
      VALUES (?, ?)
      ON CONFLICT(key) DO UPDATE SET value=excluded.value
    ''', (key, str(value)))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

# ----------------------------
# Logging helper
# ----------------------------
def log(msg):
    ts = time.strftime('%H:%M:%S')
    entry = f'[{ts}] {msg}'
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG_MESSAGES:
        del log_messages[:-MAX_LOG_MESSAGES]
    print(entry)

# ----------------------------
# Modbus initialization
# ----------------------------
def init_modbus():
    global fallback_mode, clients
    clients = []
    success = True
    for u in UNITS:
        try:
            inst = minimalmodbus.Instrument(RS485_PORT, u['slave_id'], mode='rtu')
            inst.serial.baudrate  = BAUDRATE
            inst.serial.parity    = minimalmodbus.serial.PARITY_EVEN
            inst.serial.stopbits  = 1
            inst.serial.bytesize  = 8
            inst.serial.timeout   = 1
            # quick test read
            if u['type']=='relay':
                inst.read_bit(0, functioncode=1)
            else:
                inst.read_register(0, functioncode=4)
            clients.append(inst)
            log(f"Modbus OK voor {u['name']} (ID {u['slave_id']})")
        except Exception as e:
            log(f"Modbus init fout {u['name']}: {e}")
            success = False
    fallback_mode = not success

# ----------------------------
# Relay helpers
# ----------------------------
def read_relay_states(idx):
    states = []
    inst = clients[idx]
    for coil in range(8):
        try:
            s = inst.read_bit(coil, functioncode=1)
            states.append('ON' if s else 'OFF')
        except:
            states.append('Err')
    return states

# ----------------------------
# Background sensor monitor
# ----------------------------
def sensor_monitor():
    while True:
        if not fallback_mode:
            readings = []
            for i,u in enumerate(UNITS):
                if u['type']=='analog':
                    inst = clients[i]
                    for ch in range(4):
                        try:
                            raw = inst.read_register(ch, functioncode=4)
                            cal = get_calibration(i, ch)
                            val = raw*cal['scale'] + cal['offset']
                            readings.append({
                                'name':     u['name'],
                                'slave_id': u['slave_id'],
                                'channel':  ch,
                                'raw':      raw,
                                'value':    round(val,2)
                            })
                        except:
                            pass
            socketio.emit('sensor_update', readings, namespace='/sensors')
        eventlet.sleep(1)

# ----------------------------
# SocketIO: Relay namespace
# ----------------------------
@socketio.on('connect', namespace='/relays')
def ws_relays_connect():
    log("SocketIO: /relays connected")
    data = []
    for i,u in enumerate(UNITS):
        if u['type']=='relay':
            data.append({
                'idx':      i,
                'name':     u['name'],
                'slave_id': u['slave_id'],
                'states':   read_relay_states(i)
            })
    emit('init_relays', data)

@socketio.on('toggle_relay', namespace='/relays')
def ws_toggle_relay(msg):
    idx   = msg['unit_idx']
    coil  = msg['coil_idx']
    inst  = clients[idx]
    try:
        cur = inst.read_bit(coil, functioncode=1)
        inst.write_bit(coil, not cur, functioncode=5)
        state = 'ON' if not cur else 'OFF'
        emit('relay_toggled', {'unit_idx': idx, 'coil_idx': coil, 'state': state})
    except Exception as e:
        emit('relay_error', {'error': str(e)})

# ----------------------------
# SocketIO: Sensors namespace
# ----------------------------
@socketio.on('connect', namespace='/sensors')
def ws_sensors_connect():
    log("SocketIO: /sensors connected")
    readings = []
    for i,u in enumerate(UNITS):
        if u['type']=='analog':
            inst = clients[i]
            for ch in range(4):
                try:
                    raw = inst.read_register(ch, functioncode=4)
                    cal = get_calibration(i, ch)
                    val = raw*cal['scale'] + cal['offset']
                    readings.append({
                        'name':     u['name'],
                        'slave_id': u['slave_id'],
                        'channel':  ch,
                        'raw':      raw,
                        'value':    round(val,2)
                    })
                except:
                    readings.append({
                        'name':     u['name'],
                        'slave_id': u['slave_id'],
                        'channel':  ch,
                        'raw':      None,
                        'value':    None
                    })
    emit('sensor_update', readings)

# ----------------------------
# SocketIO: Calibration namespace
# ----------------------------
@socketio.on('connect', namespace='/cal')
def ws_cal_connect():
    log("SocketIO: /cal connected")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      SELECT unit_index, channel, scale, offset, phys_min, phys_max
      FROM calibration
    ''')
    all_cal = {}
    for unit, ch, sc, off, pmin, pmax in c.fetchall():
        all_cal[f"{unit}-{ch}"] = {
            'scale':    sc,
            'offset':   off,
            'phys_min': pmin,
            'phys_max': pmax
        }
    conn.close()
    emit('init_cal', all_cal)

@socketio.on('set_cal_points', namespace='/cal')
def ws_set_cal(msg):
    unit     = msg['unit']
    channel  = msg['channel']
    raw1     = msg['raw1']
    phys1    = msg['phys1']
    raw2     = msg['raw2']
    phys2    = msg['phys2']
    try:
        if raw1 == raw2:
            raise ValueError("raw1 en raw2 mogen niet gelijk zijn")
        scale   = (phys2 - phys1) / (raw2 - raw1)
        offset  = phys1 - scale * raw1
        save_calibration(unit, channel, scale, offset, phys1, phys2)
        log(f"Calibration saved unit{unit} ch{channel}: scale={scale:.4f}, offset={offset:.2f}, min={phys1}, max={phys2}")
        emit('cal_saved', {
            'unit':     unit,
            'channel':  channel,
            'scale':    scale,
            'offset':   offset,
            'phys_min': phys1,
            'phys_max': phys2
        })
    except Exception as e:
        emit('cal_error', {'error': str(e)})

# ----------------------------
# WebSocket: EX04AIO namespace
# ----------------------------
@socketio.on('connect', namespace='/aio')
def ws_aio_connect(auth):
    # stuur initial state
    idx = next(i for i,u in enumerate(UNITS) if u['type']=='aio')
    inst = clients[idx]
    rows = []
    for ch in range(4):
        raw_out  = inst.read_register(ch, functioncode=3)
        phys_out = round((raw_out/4095.0)*20.0, 2)
        pct      = round((phys_out-4.0)/16.0*100.0, 1) if phys_out > 4.0 else None
        rows.append({
            'channel':     ch,
            'raw_out':     raw_out,
            'phys_out':    phys_out,
            'percent_out': pct
        })
    emit('aio_init', rows)

@socketio.on('aio_set', namespace='/aio')
def ws_aio_set(msg):
    idx     = next(i for i,u in enumerate(UNITS) if u['type']=='aio')
    ch      = msg['channel']
    percent = float(msg['percent'])
    # % → mA → raw
    mA  = 4.0 + (percent/100.0)*16.0
    raw = int((mA/20.0)*4095)
    clients[idx].write_register(ch, raw, functioncode=6)
    # back to client
    emit('aio_updated', {
        'channel':     ch,
        'raw_out':     raw,
        'phys_out':    round(mA,2),
        'percent_out': percent
    })


# ----------------------------
# HTTP Routes
# ----------------------------
@app.route('/')
def index():
    return render_template('dashboard.html', fallback_mode=fallback_mode)

@app.route('/relays')
def relays():
    return render_template('relays.html')

@app.route('/sensors')
def sensors():
    return render_template('sensors.html')

@app.route('/aio')
def aio():
    # Nu alleen nog de template serveren.
    return render_template('aio.html', fallback_mode=fallback_mode)

@app.route('/calibrate')
def calibrate():
    return render_template('calibrate.html', units=UNITS)

# ----------------------------
# Main
# ----------------------------
if __name__ == '__main__':
    init_db()
    init_modbus()
    socketio.start_background_task(sensor_monitor)
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, use_reloader=False)
