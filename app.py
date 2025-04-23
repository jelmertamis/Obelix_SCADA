# app.py
import time
import sqlite3
import logging

import minimalmodbus
import serial
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

# ─── Configuration ──────────────────────────────────────────────────────────
RS485_PORT = '/dev/ttyUSB0'       # Pas aan naar jouw poort
BAUDRATE   = 9600
PARITY     = serial.PARITY_EVEN
STOPBITS   = 1
BYTESIZE   = 8
TIMEOUT    = 1                    # seconden

DB_FILE = 'settings.db'

UNITS = [
    {'slave_id': 1,  'name': 'Relay Module 1', 'type': 'relay'},
    {'slave_id': 2,  'name': 'Relay Module 2', 'type': 'relay'},
    {'slave_id': 3,  'name': 'Relay Module 3', 'type': 'relay'},
    {'slave_id': 4,  'name': 'Relay Module 4', 'type': 'relay'},
    {'slave_id': 5,  'name': 'Analog Input 1','type': 'analog'},
    {'slave_id': 6,  'name': 'Analog Input 2','type': 'analog'},
    {'slave_id': 7,  'name': 'Analog Input 3','type': 'analog'},
    {'slave_id': 8,  'name': 'Analog Input 4','type': 'analog'},
    {'slave_id': 9,  'name': 'EX1608DD',      'type': 'relay'},
    {'slave_id': 10, 'name': 'EX04AIO',        'type': 'aio'},
]
AIO_IDX = next(i for i,u in enumerate(UNITS) if u['type']=='aio')

clients       = []
fallback_mode = False
log_messages  = []
MAX_LOG       = 20

# ─── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
def log(msg):
    ts = time.strftime('%H:%M:%S')
    entry = f'[{ts}] {msg}'
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG:
        del log_messages[:-MAX_LOG]
    print(entry)

# ─── Database helpers ───────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS calibration (
        unit_index INTEGER NOT NULL,
        channel     INTEGER NOT NULL,
        scale       REAL    NOT NULL,
        offset      REAL    NOT NULL,
        phys_min    REAL    NOT NULL,
        phys_max    REAL    NOT NULL,
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

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      INSERT INTO settings(key, value) VALUES (?, ?)
      ON CONFLICT(key) DO UPDATE SET value=excluded.value
    ''', (key, str(value)))
    conn.commit()
    conn.close()

def get_calibration(unit_index, channel):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      SELECT scale, offset FROM calibration
      WHERE unit_index=? AND channel=?
    ''', (unit_index, channel))
    row = c.fetchone()
    conn.close()
    if row:
        return {'scale': row[0], 'offset': row[1]}
    return {'scale': 1.0, 'offset': 0.0}

def save_calibration(unit_index, channel, scale, offset, phys_min, phys_max):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      INSERT INTO calibration(unit_index,channel,scale,offset,phys_min,phys_max)
      VALUES(?,?,?,?,?,?)
      ON CONFLICT(unit_index,channel) DO UPDATE SET
        scale=excluded.scale, offset=excluded.offset,
        phys_min=excluded.phys_min, phys_max=excluded.phys_max
    ''', (unit_index, channel, scale, offset, phys_min, phys_max))
    conn.commit()
    conn.close()

# ─── Dummy Modbus fallback ──────────────────────────────────────────────────
class DummyModbusClient:
    def __init__(self, *args, **kwargs):
        self._ctr = 0
    def read_bit(self, coil, functioncode=None):
        self._ctr += 1
        return (self._ctr % 2) == 0
    def write_bit(self, coil, state, functioncode=None): pass
    def read_register(self, reg, functioncode=None):
        self._ctr += 1
        return (self._ctr * 137) % 4096
    def write_register(self, reg, value, functioncode=None): pass

# ─── Modbus initialization ─────────────────────────────────────────────────
def init_modbus():
    global fallback_mode, clients
    clients = []
    try:
        for u in UNITS:
            inst = minimalmodbus.Instrument(RS485_PORT, u['slave_id'], mode=minimalmodbus.MODE_RTU)
            inst.serial.baudrate   = BAUDRATE
            inst.serial.parity     = minimalmodbus.serial.PARITY_EVEN
            inst.serial.stopbits   = STOPBITS
            inst.serial.bytesize   = BYTESIZE
            inst.serial.timeout    = TIMEOUT
            inst.clear_buffers_before_each_transaction = True

            # quick test
            if u['type']=='relay':
                inst.read_bit(0, functioncode=1)
            else:
                inst.read_register(0, functioncode=4)

            clients.append(inst)
            log(f"Modbus OK voor {u['name']} (ID {u['slave_id']})")
        fallback_mode = False
    except Exception as e:
        log(f"Modbus niet gevonden ({e}), overschakelen naar Dummy‐modus.")
        clients = [DummyModbusClient() for _ in UNITS]
        fallback_mode = True

# ─── Sensor monitor ─────────────────────────────────────────────────────────
def sensor_monitor():
    while True:
        data = []
        for i,u in enumerate(UNITS):
            if u['type']=='analog':
                inst = clients[i]
                for ch in range(4):
                    try:
                        raw = inst.read_register(ch, functioncode=4)
                        cal = get_calibration(i, ch)
                        val = raw * cal['scale'] + cal['offset']
                        data.append({
                            'name':     u['name'],
                            'slave_id': u['slave_id'],
                            'channel':  ch,
                            'raw':      raw,
                            'value':    round(val, 2)
                        })
                    except:
                        pass
        # debug-only slave 5
        slave5 = [d for d in data if d['slave_id']==5]
        if slave5:
            print(f"[DBG sensor_monitor] Slave 5: {slave5}")
        socketio.emit('sensor_update', data, namespace='/sensors')
        time.sleep(1)

# ─── Flask + SocketIO setup ────────────────────────────────────────────────
app = Flask(__name__, static_folder='static')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ─── Relay helper using read_bits ───────────────────────────────────────────
def read_relay_states(idx):
    inst = clients[idx]
    try:
        # Read 8 coils in one call
        bits = inst.read_bits(0, 8, functioncode=1)
    except Exception:
        # Fallback: one-by-one
        bits = []
        for coil in range(8):
            try:
                bits.append(inst.read_bit(coil, functioncode=1))
            except:
                bits.append(False)
    return ['ON' if b else 'OFF' for b in bits]

# ─── WebSocket: Relays ──────────────────────────────────────────────────────
@socketio.on('connect', namespace='/relays')
def ws_relays_connect(auth):
    log("SocketIO: /relays connected")
    out = []
    for i,u in enumerate(UNITS):
        if u['type']=='relay':
            out.append({
                'idx':      i,
                'name':     u['name'],
                'slave_id': u['slave_id'],
                'states':   read_relay_states(i)
            })
    emit('init_relays', out)

@socketio.on('toggle_relay', namespace='/relays')
def ws_toggle_relay(msg):
    idx, coil = msg['unit_idx'], msg['coil_idx']
    inst = clients[idx]
    try:
        cur = inst.read_bit(coil, functioncode=1)
        inst.write_bit(coil, not cur, functioncode=5)
        state = 'ON' if not cur else 'OFF'
        emit('relay_toggled', {'unit_idx':idx,'coil_idx':coil,'state':state})
    except Exception as e:
        emit('relay_error', {'error':str(e)})

# ─── WebSocket: Sensors ─────────────────────────────────────────────────────
@socketio.on('connect', namespace='/sensors')
def ws_sensors_connect(auth):
    log("SocketIO: /sensors connected")
    # sensor_monitor runs in the background

# ─── Other WebSocket handlers (calibration, aio, r302) ─────────────────────
# ... (unchanged from previous full app) ...

# ─── HTTP Routes ───────────────────────────────────────────────────────────
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.route('/')
def index():
    return render_template('dashboard.html', fallback_mode=fallback_mode)

@app.route('/relays')
def relays():
    relay_units = []
    for i,u in enumerate(UNITS):
        if u['type']=='relay':
            relay_units.append({
                'idx':  i,
                'id':   u['slave_id'],
                'name': u['name'],
                'coils': [s=='ON' for s in read_relay_states(i)]
            })
    return render_template('relays.html', relays=relay_units)

@app.route('/sensors')
def sensors():
    return render_template('sensors.html')

# ... other routes for calibrate, aio, r302 ...

# ─── Main ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    init_modbus()
    socketio.start_background_task(sensor_monitor)
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, use_reloader=False)
