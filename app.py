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
# Relay status reader
# ----------------------------
def read_relay_states(unit_idx):
    states = []
    for ch in range(8):
        try:
            s = clients[unit_idx].read_bit(ch, functioncode=1)
            states.append('ON' if s else 'OFF')
        except:
            states.append('Err')
    return states

# ----------------------------
# WebSocket: Relay handlers
# ----------------------------
@socketio.on('connect', namespace='/relays')
def ws_relay_connect():
    log("Client verbonden op WebSocket /relays")
    relays = []
    for i, u in enumerate(UNITS):
        if u['type'] == 'relay':
            relays.append({
                'idx':      i,
                'name':     u['name'],
                'slave_id': u['slave_id'],
                'states':   read_relay_states(i)
            })
    emit('init_relays', relays)

@socketio.on('toggle_relay', namespace='/relays')
def ws_toggle_relay(data):
    i  = data['unit_idx']
    ch = data['coil_idx']
    try:
        cur = clients[i].read_bit(ch, functioncode=1)
        clients[i].write_bit(ch, not cur, functioncode=5)
        new_state = 'ON' if not cur else 'OFF'
        emit('relay_toggled', {
            'unit_idx': i,
            'coil_idx': ch,
            'state':    new_state
        })
    except Exception as e:
        emit('relay_error', {'error': str(e)})

# ----------------------------
# Sensor monitor (background)
# ----------------------------
def sensor_monitor():
    while True:
        if not fallback_mode:
            readings = []
            for i, u in enumerate(UNITS):
                if u['type'] == 'analog':
                    for ch in range(4):
                        try:
                            raw = clients[i].read_register(ch, functioncode=4)
                            cal = get_calibration(i, ch)
                            val = raw * cal['scale'] + cal['offset']
                            readings.append({
                                'name':     u['name'],
                                'slave_id': u['slave_id'],
                                'channel':  ch,
                                'raw':      raw,
                                'value':    round(val, 2)
                            })
                        except:
                            pass
            socketio.emit('sensor_update', readings, namespace='/sensors')
        eventlet.sleep(2)

# ----------------------------
# HTTP Routes
# ----------------------------
@app.route('/')
def index():
    return render_template('newtest_all_units.html',
                           fallback_mode=fallback_mode)

@app.route('/relays')
def relays():
    return render_template('relays.html')

@app.route('/sensors')
def sensors():
    return render_template('sensors.html', fallback_mode=fallback_mode)

@app.route('/aio', methods=['GET', 'POST'])
def aio():
    # your existing /aio logic here...
    pass

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
