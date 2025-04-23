import time
import sqlite3
import logging
from threading import Lock

import minimalmodbus
import serial
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# ─── Configuration ──────────────────────────────────────────────────────────
RS485_PORT = '/dev/ttyUSB0'
BAUDRATE   = 9600
PARITY     = minimalmodbus.serial.PARITY_EVEN
STOPBITS   = 1
BYTESIZE   = 8
TIMEOUT    = 1

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

# ─── Concurrency lock voor RS-485 ───────────────────────────────────────────
modbus_lock = Lock()

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
            inst.serial.parity     = PARITY
            inst.serial.stopbits   = STOPBITS
            inst.serial.bytesize   = BYTESIZE
            inst.serial.timeout    = TIMEOUT
            inst.clear_buffers_before_each_transaction = True

            # quick test
            with modbus_lock:
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
                        with modbus_lock:
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
        socketio.emit('sensor_update', data, namespace='/sensors')
        time.sleep(1)

# ─── Flask + SocketIO setup ────────────────────────────────────────────────
app = Flask(__name__, static_folder='static')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ─── Relay helper using batch read_bits ────────────────────────────────────
def read_relay_states(idx):
    inst = clients[idx]
    with modbus_lock:
        try:
            bits = inst.read_bits(0, 8, functioncode=1)
        except Exception:
            bits = []
            for coil in range(8):
                try:
                    bits.append(inst.read_bit(coil, functioncode=1))
                except:
                    bits.append(False)
    return bits

# ─── WebSocket: Relays ──────────────────────────────────────────────────────
@socketio.on('connect', namespace='/relays')
def ws_relays_connect(auth):
    log("SocketIO: /relays connected")
    out = []
    for i,u in enumerate(UNITS):
        if u['type']=='relay':
            states = read_relay_states(i)
            out.append({
                'idx':    i,
                'name':   u['name'],
                'states': states
            })
    emit('init_relays', out, namespace='/relays')

@socketio.on('toggle_relay', namespace='/relays')
def ws_toggle_relay(msg):
    idx   = msg['unit_idx']
    coil  = msg['coil_idx']
    want  = msg['state']  # "ON" of "OFF"

    # 1) Log de binnenkomende request
    log(f"🔄 Relay change requested: unit {idx}, coil {coil} → {want}")

    inst  = clients[idx]
    try:
        # 2) Schakel de coil
        with modbus_lock:
            if want == 'ON':
                inst.write_bit(coil, True, functioncode=5)
            else:
                inst.write_bit(coil, False, functioncode=5)

        # 3) Broadcast naar clients
        emit('relay_toggled', {
            'unit_idx': idx,
            'coil_idx': coil,
            'state':    want
        }, namespace='/relays', broadcast=True)

        # 4) Log het succes
        log(f"✅ Relay changed: unit {idx}, coil {coil} is now {want}")

    except Exception as e:
        # 5) Log de fout
        log(f"⚠️ Modbus error toggling unit {idx}, coil {coil}: {e}")
        emit('relay_error', {'error': str(e)}, namespace='/relays')


# ─── WebSocket: Sensors ─────────────────────────────────────────────────────
@socketio.on('connect', namespace='/sensors')
def ws_sensors_connect(auth):
    log("SocketIO: /sensors connected")
    # sensor_monitor draait al op de achtergrond

# ─── WebSocket: Calibration ─────────────────────────────────────────────────
@socketio.on('connect', namespace='/cal')
def ws_cal_connect(auth):
    log("SocketIO: /cal connected")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT unit_index,channel,scale,offset,phys_min,phys_max FROM calibration')
    payload = {}
    for u,ch,sc,off,pmin,pmax in c.fetchall():
        payload[f"{u}-{ch}"] = {
            'scale':sc,'offset':off,
            'phys_min':pmin,'phys_max':pmax
        }
    conn.close()
    emit('init_cal', payload, namespace='/cal')

@socketio.on('set_cal_points', namespace='/cal')
def ws_set_cal(msg):
    u,ch,raw1,phys1,raw2,phys2 = (
        msg['unit'], msg['channel'],
        msg['raw1'], msg['phys1'],
        msg['raw2'], msg['phys2']
    )
    try:
        if raw1 == raw2:
            raise ValueError("raw1 en raw2 mogen niet gelijk zijn")
        scale  = (phys2-phys1)/(raw2-raw1)
        offset = phys1 - scale*raw1
        save_calibration(u, ch, scale, offset, phys1, phys2)
        emit('cal_saved', {
            'unit':u,'channel':ch,
            'scale':scale,'offset':offset,
            'phys_min':phys1,'phys_max':phys2
        }, namespace='/cal')
    except Exception as e:
        emit('cal_error', {'error': str(e)}, namespace='/cal')

# ─── WebSocket: EX04AIO ─────────────────────────────────────────────────────
@socketio.on('connect', namespace='/aio')
def ws_aio_connect(auth):
    log("SocketIO: /aio connected")
    rows = []
    inst = clients[AIO_IDX]
    for ch in range(4):
        with modbus_lock:
            raw_out  = inst.read_register(ch, functioncode=3)
        phys_out = round((raw_out/4095.0)*20.0,2)
        pct      = round((phys_out-4.0)/16.0*100.0,1) if phys_out>4.0 else None
        rows.append({
            'channel':    ch,
            'raw_out':    raw_out,
            'phys_out':   phys_out,
            'percent_out':pct
        })
    emit('aio_init', rows, namespace='/aio')

@socketio.on('aio_set', namespace='/aio')
def ws_aio_set(msg):
    ch,pct = msg['channel'], float(msg['percent'])
    mA      = 4.0 + (pct/100.0)*16.0
    raw     = int((mA/20.0)*4095)
    inst    = clients[AIO_IDX]
    with modbus_lock:
        inst.write_register(ch, raw, functioncode=6)
    emit('aio_updated', {
      'channel':    ch,
      'raw_out':    raw,
      'phys_out':   round(mA,2),
      'percent_out':pct
    }, namespace='/aio')

# ─── WebSocket: R302 ───────────────────────────────────────────────────────
DEFAULT_PUMP_MODE       = 'AUTO'
DEFAULT_COMPRESSOR_MODE = 'OFF'

@socketio.on('connect', namespace='/r302')
def ws_r302_connect(auth):
    log("SocketIO: /r302 connected")
    sensors = [{'name':f'Sensor {i+1}','raw':None,'value':None} for i in range(4)]
    pumps = {
        k: get_setting(f'pump_{k}_mode', DEFAULT_PUMP_MODE)
        for k in ('influent','nutrient','effluent')
    }
    compressors = {
        num: {
            'mode': get_setting(f'compressor{num}_mode', DEFAULT_COMPRESSOR_MODE),
            'freq': float(get_setting(f'compressor{num}_freq', 0.0))
        }
        for num in (1,2)
    }
    emit('r302_init', {
        'sensors':      sensors,
        'pumps':        pumps,
        'compressors':  compressors
    }, namespace='/r302')

@socketio.on('set_pump_mode', namespace='/r302')
def ws_set_pump_mode(msg):
    pump,mode = msg['pump'], msg['mode']
    set_setting(f'pump_{pump}_mode', mode)
    emit('pump_mode_updated', {'pump':pump,'mode':mode}, namespace='/r302', broadcast=True)

@socketio.on('set_compressor_mode', namespace='/r302')
def ws_set_compressor_mode(msg):
    num,mode = msg['compressor'], msg['mode']
    set_setting(f'compressor{num}_mode', mode)
    emit('compressor_mode_updated', {'compressor':num,'mode':mode}, namespace='/r302', broadcast=True)

@socketio.on('set_compressor_freq', namespace='/r302')
def ws_set_compressor_freq(msg):
    num,freq = msg['compressor'], float(msg['freq'])
    set_setting(f'compressor{num}_freq', freq)
    emit('compressor_freq_updated', {'compressor':num,'freq':freq}, namespace='/r302', broadcast=True)

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
                'idx':        i,
                'slave_id':   u['slave_id'],
                'name':       u['name'],
                'coil_count': 8
            })
    return render_template('relays.html', relays=relay_units)

@app.route('/sensors')
def sensors():
    return render_template('sensors.html')

@app.route('/calibrate')
def calibrate():
    return render_template('calibrate.html', units=UNITS)

@app.route('/aio')
def aio():
    return render_template('aio.html', fallback_mode=fallback_mode)

@app.route('/r302')
def r302():
    return render_template('R302.html')

if __name__ == '__main__':
    init_db()
    init_modbus()
    socketio.start_background_task(sensor_monitor)
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, use_reloader=False)
