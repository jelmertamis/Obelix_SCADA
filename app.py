import sqlite3
import time
import eventlet

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import minimalmodbus

# ----------------------------
# Dummy client for automatic fallback
# ----------------------------
class DummyModbusClient:
    """Simuleert een minimalmodbus.Instrument met steeds veranderende waarden."""
    def __init__(self, *args, **kwargs):
        self._counter = 0

    def read_bit(self, coil, functioncode=None):
        self._counter += 1
        return (self._counter % 2) == 0

    def write_bit(self, coil, state, functioncode=None):
        pass

    def read_register(self, reg, functioncode=None):
        self._counter += 1
        return (self._counter * 137) % 4096

    def write_register(self, reg, value, functioncode=None):
        pass

# ----------------------------
# Configuration
# ----------------------------
RS485_PORT = '/dev/ttyUSB0'
BAUDRATE   = 9600
DB_FILE    = 'settings.db'

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

# ----------------------------
# Flask & SocketIO setup
# ----------------------------
app      = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

# ----------------------------
# Globals
# ----------------------------
clients       = []
fallback_mode = False
log_messages  = []
MAX_LOG       = 20

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
        phys_min   REAL    NOT NULL,
        phys_max   REAL    NOT NULL,
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
      INSERT INTO settings(key, value)
      VALUES (?, ?)
      ON CONFLICT(key) DO UPDATE SET value=excluded.value
    ''', (key, str(value)))
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
        return {'scale':row[0],'offset':row[1],
                'phys_min':row[2],'phys_max':row[3]}
    return {'scale':1.0,'offset':0.0,'phys_min':0.0,'phys_max':4095.0}

def save_calibration(unit, channel, scale, offset, pmin, pmax):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      INSERT INTO calibration(unit_index,channel,scale,offset,phys_min,phys_max)
      VALUES(?,?,?,?,?,?)
      ON CONFLICT(unit_index,channel) DO UPDATE SET
        scale=excluded.scale, offset=excluded.offset,
        phys_min=excluded.phys_min, phys_max=excluded.phys_max
    ''', (unit, channel, scale, offset, pmin, pmax))
    conn.commit()
    conn.close()

# ----------------------------
# Logging helper
# ----------------------------
def log(msg):
    ts = time.strftime('%H:%M:%S')
    entry = f'[{ts}] {msg}'
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG:
        del log_messages[:-MAX_LOG]
    print(entry)

# ----------------------------
# Modbus initialization with automatic fallback
# ----------------------------
def init_modbus():
    global fallback_mode, clients
    clients = []
    try:
        for u in UNITS:
            inst = minimalmodbus.Instrument(RS485_PORT, u['slave_id'], mode='rtu')
            inst.serial.baudrate = BAUDRATE
            inst.serial.parity   = minimalmodbus.serial.PARITY_EVEN
            inst.serial.stopbits = 1
            inst.serial.bytesize = 8
            inst.serial.timeout  = 1
            # test-read
            if u['type']=='relay':
                inst.read_bit(0, functioncode=1)
            else:
                inst.read_register(0, functioncode=4)
            clients.append(inst)
            log(f"Modbus OK voor {u['name']} (ID {u['slave_id']})")
        fallback_mode = False
    except Exception as e:
        log(f"Modbus niet gevonden ({e}), overschakelen naar Dummy-modus.")
        clients = [DummyModbusClient() for _ in UNITS]
        fallback_mode = False

# ----------------------------
# Sensor background monitor
# ----------------------------
def sensor_monitor():
    while True:
        if not fallback_mode:
            data = []
            for i,u in enumerate(UNITS):
                if u['type']=='analog':
                    inst = clients[i]
                    for ch in range(4):
                        try:
                            raw = inst.read_register(ch, functioncode=4)
                            cal = get_calibration(i, ch)
                            val = raw*cal['scale'] + cal['offset']
                            data.append({
                                'name':     u['name'],
                                'slave_id': u['slave_id'],
                                'channel':  ch,
                                'raw':      raw,
                                'value':    round(val,2)
                            })
                        except: pass
            socketio.emit('sensor_update', data, namespace='/sensors')
        eventlet.sleep(1)

# ----------------------------
# WebSocket: Relays
# ----------------------------
def read_relay_states(idx):
    inst = clients[idx]
    states = []
    for coil in range(8):
        try:
            s = inst.read_bit(coil, functioncode=1)
            states.append('ON' if s else 'OFF')
        except:
            states.append('Err')
    return states

@socketio.on('connect', namespace='/relays')
def ws_relays_connect(auth):
    log("SocketIO: /relays connected")
    out=[]
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

# ----------------------------
# WebSocket: Sensors
# ----------------------------
@socketio.on('connect', namespace='/sensors')
def ws_sensors_connect(auth):
    log("SocketIO: /sensors connected")
    sensor_monitor()

# ----------------------------
# WebSocket: Calibration
# ----------------------------
@socketio.on('connect', namespace='/cal')
def ws_cal_connect(auth):
    log("SocketIO: /cal connected")
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT unit_index,channel,scale,offset,phys_min,phys_max FROM calibration')
    payload = {}
    for u,ch,sc,off,pmin,pmax in c.fetchall():
        payload[f"{u}-{ch}"] = {
            'scale':    sc,
            'offset':   off,
            'phys_min': pmin,
            'phys_max': pmax
        }
    conn.close()
    emit('init_cal', payload)

@socketio.on('set_cal_points', namespace='/cal')
def ws_set_cal(msg):
    u,ch,raw1,phys1,raw2,phys2 = (
        msg['unit'], msg['channel'],
        msg['raw1'], msg['phys1'],
        msg['raw2'], msg['phys2']
    )
    try:
        if raw1==raw2:
            raise ValueError("raw1 en raw2 mogen niet gelijk zijn")
        scale  = (phys2-phys1)/(raw2-raw1)
        offset = phys1 - scale*raw1
        save_calibration(u,ch,scale,offset,phys1,phys2)
        emit('cal_saved', {
            'unit':u,'channel':ch,
            'scale':scale,'offset':offset,
            'phys_min':phys1,'phys_max':phys2
        })
    except Exception as e:
        emit('cal_error', {'error':str(e)})

# ----------------------------
# WebSocket: EX04AIO
# ----------------------------
@socketio.on('connect', namespace='/aio')
def ws_aio_connect(auth):
    log("SocketIO: /aio connected")
    rows=[]; inst=clients[AIO_IDX]
    for ch in range(4):
        raw_out  = inst.read_register(ch, functioncode=3)
        phys_out = round((raw_out/4095.0)*20.0,2)
        pct      = round((phys_out-4.0)/16.0*100.0,1) if phys_out>4.0 else None
        rows.append({'channel':ch,'raw_out':raw_out,
                     'phys_out':phys_out,'percent_out':pct})
    emit('aio_init', rows)

@socketio.on('aio_set', namespace='/aio')
def ws_aio_set(msg):
    ch, pct = msg['channel'], float(msg['percent'])
    mA      = 4.0 + (pct/100.0)*16.0
    raw     = int((mA/20.0)*4095)
    inst    = clients[AIO_IDX]
    inst.write_register(ch, raw, functioncode=6)
    emit('aio_updated', {
        'channel':ch,'raw_out':raw,
        'phys_out':round(mA,2),'percent_out':pct
    })

# ----------------------------
# WebSocket: R302
# ----------------------------
DEFAULT_PUMP_MODE       = 'AUTO'
DEFAULT_COMPRESSOR_MODE = 'OFF'

@socketio.on('connect', namespace='/r302')
def ws_r302_connect(auth):
    log("SocketIO: /r302 connected")
    sensors = [{'name':f'Sensor {i+1}','raw':None,'value':None} for i in range(4)]
    pumps = {k: get_setting(f'pump_{k}_mode', DEFAULT_PUMP_MODE)
             for k in ('influent','nutrient','effluent')}
    compressors = {
        num: {'mode': get_setting(f'compressor{num}_mode', DEFAULT_COMPRESSOR_MODE),
              'freq': float(get_setting(f'compressor{num}_freq', 0.0))}
        for num in (1,2)
    }
    emit('r302_init', {
        'sensors':     sensors,
        'pumps':       pumps,
        'compressors': compressors
    })

@socketio.on('set_pump_mode', namespace='/r302')
def ws_set_pump_mode(msg):
    pump, mode = msg['pump'], msg['mode']
    set_setting(f'pump_{pump}_mode', mode)
    emit('pump_mode_updated', {'pump':pump,'mode':mode}, namespace='/r302', broadcast=True)

@socketio.on('set_compressor_mode', namespace='/r302')
def ws_set_compressor_mode(msg):
    num, mode = msg['compressor'], msg['mode']
    set_setting(f'compressor{num}_mode', mode)
    emit('compressor_mode_updated',
         {'compressor':num,'mode':mode}, namespace='/r302', broadcast=True)

@socketio.on('set_compressor_freq', namespace='/r302')
def ws_set_compressor_freq(msg):
    num, freq = msg['compressor'], float(msg['freq'])
    set_setting(f'compressor{num}_freq', freq)
    emit('compressor_freq_updated',
         {'compressor':num,'freq':freq}, namespace='/r302', broadcast=True)

# ----------------------------
# HTTP Routes
# ----------------------------
app.config['TEMPLATES_AUTO_RELOAD'] = True
@app.route('/')
def index():
    return render_template('dashboard.html', fallback_mode=fallback_mode)

@app.route('/relays')
def relays():
    relay_units = []
    for i, u in enumerate(UNITS):
        if u['type'] == 'relay':
            states = read_relay_states(i)
            relay_units.append({
                'idx': i,
                'id': u['slave_id'],
                'name': u['name'],
                'coils': [s == 'ON' for s in states]
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

# ----------------------------
# Main
# ----------------------------
if __name__ == '__main__':
    init_db()
    init_modbus()
    socketio.start_background_task(sensor_monitor)
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, use_reloader=True)
