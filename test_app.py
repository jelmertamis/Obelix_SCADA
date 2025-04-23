# test_app.py
import time
import logging
import sqlite3
import serial

import minimalmodbus
from flask import Flask
from flask_socketio import SocketIO

# ─── Configuratie ───────────────────────────────────────────────────────────
RS485_PORT = '/dev/ttyUSB0'   # Pas aan als nodig
BAUDRATE   = 9600
PARITY     = serial.PARITY_EVEN
STOPBITS   = 1
BYTESIZE   = 8
TIMEOUT    = 1

SLAVE_ID = 5
CHANNELS = 4

DB_FILE  = 'settings.db'

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Flask + SocketIO setup ─────────────────────────────────────────────────
app = Flask(__name__, static_folder='static')
# Stap 1: forceer threading-mode zodat gewone threads werken
socketio = SocketIO(app,
                    cors_allowed_origins='*',
                    async_mode='threading')

@app.route('/')
def index():
    # Serveert static/sensor_test.html
    return app.send_static_file('sensor_test.html')

# ─── Kalibratie helper ───────────────────────────────────────────────────────
def get_calibration(channel):
    try:
        conn = sqlite3.connect(DB_FILE)
        c    = conn.cursor()
        c.execute(
            'SELECT scale, offset FROM calibration WHERE unit_index=0 AND channel=?',
            (channel,)
        )
        row = c.fetchone()
        conn.close()
        if row:
            return {'scale': row[0], 'offset': row[1]}
    except Exception:
        pass
    return {'scale': 1.0, 'offset': 0.0}

# ─── Modbus‐instrument initialisatie ─────────────────────────────────────────
def init_client():
    inst = minimalmodbus.Instrument(RS485_PORT, SLAVE_ID, mode=minimalmodbus.MODE_RTU)
    inst.serial.baudrate   = BAUDRATE
    inst.serial.parity     = PARITY
    inst.serial.stopbits   = STOPBITS
    inst.serial.bytesize   = BYTESIZE
    inst.serial.timeout    = TIMEOUT
    inst.clear_buffers_before_each_transaction = True
    inst.debug = False

    try:
        inst.read_register(0, functioncode=4)
        log.info(f"✔ Modbus OK voor slave {SLAVE_ID}")
    except Exception as e:
        log.error(f"✖ Kan slave {SLAVE_ID} niet bereiken: {e}")
    return inst

# ─── Achtergrond‐task: uitlezen + emit ───────────────────────────────────────
def sensor_loop(inst):
    while True:
        for ch in range(CHANNELS):
            try:
                raw = inst.read_register(ch,
                                         number_of_decimals=0,
                                         functioncode=4)
                cal = get_calibration(ch)
                val = raw * cal['scale'] + cal['offset']
                # Print naar server-console
                print(f"[{time.strftime('%H:%M:%S')}] Ch{ch}: raw={raw}  value={val:.2f}")
                # Zend via SocketIO
                socketio.emit('sensor_update', {
                    'channel': ch,
                    'raw':      raw,
                    'value':    val
                })
            except Exception as e:
                log.warning(f"Fout bij uitlezen Ch{ch}: {e}")
            time.sleep(0.1)
        time.sleep(2)

# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    client = init_client()
    # Stap 2: gebruik SocketIO background task
    socketio.start_background_task(sensor_loop, client)
    # Run op 5002
    socketio.run(app, host='0.0.0.0', port=5002)
