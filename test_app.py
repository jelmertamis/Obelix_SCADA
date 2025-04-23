# test_app.py
# Zelf‐contained Flask + SocketIO server die:
# 1) Eenvoudig je static HTML page serveert
# 2) Slave ID 5 uitleest via MinimalModbus
# 3) De waarden in de console logt èn via WebSockets pusht naar de browser

import time
import threading
import logging
import sqlite3
import serial

import minimalmodbus
from flask import Flask
from flask_socketio import SocketIO

# ─── Configuratie ───────────────────────────────────────────────────────────
RS485_PORT = '/dev/ttyUSB0'   # Pas aan: bv. 'COM3' op Windows
BAUDRATE   = 9600
PARITY     = serial.PARITY_EVEN
STOPBITS   = 1
BYTESIZE   = 8
TIMEOUT    = 1                # in seconden

SLAVE_ID   = 5                # Alleen slave ID 5 uitlezen
CHANNELS   = 4                # Aantal kanalen per module

DB_FILE    = 'settings.db'    # SQLite DB voor kalibratie (optioneel)

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Flask & SocketIO setup ─────────────────────────────────────────────────
app      = Flask(__name__, static_folder='static')
socketio = SocketIO(app, cors_allowed_origins='*')

@app.route('/')
def index():
    # Serveert het bestand static/sensor_test.html
    return app.send_static_file('sensor_test.html')

# ─── Kalibratie helper ───────────────────────────────────────────────────────
def get_calibration(channel):
    # Haal scale & offset op uit settings.db, of fallback naar 1.0/0.0
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            'SELECT scale, offset FROM calibration WHERE unit_index=? AND channel=?',
            (0, channel)
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
    inst.debug = False  # op True voor RTU-trace in console

    try:
        inst.read_register(0, functioncode=4)
        log.info(f"✔ Modbus OK voor slave {SLAVE_ID}")
    except Exception as e:
        log.error(f"✖ Kan slave {SLAVE_ID} niet bereiken: {e}")
    return inst

# ─── Achtergrond‐thread: sensoren uitlezen + emit ────────────────────────────
def sensor_loop(inst):
    """Lees elke 2s slave SLAVE_ID uit, print en zend via WebSocket."""
    while True:
        for ch in range(CHANNELS):
            try:
                raw = inst.read_register(
                    registeraddress=ch,
                    number_of_decimals=0,
                    functioncode=4
                )
                cal = get_calibration(ch)
                val = raw * cal['scale'] + cal['offset']
                # Print naar server-console
                print(f"[{time.strftime('%H:%M:%S')}] Slave {SLAVE_ID} Ch{ch}: raw={raw}  value={val:.2f}")
                # Zend naar alle clients
                socketio.emit('sensor_update', {
                    'channel': ch,
                    'raw':      raw,
                    'value':    val
                })
            except Exception as e:
                log.warning(f"Fout bij uitlezen Ch{ch}: {e}")
            time.sleep(0.1)  # korte pauze tussen kanalen
        time.sleep(2)  # herhaal elke 2 seconden

if __name__ == '__main__':
    client = init_client()
    threading.Thread(target=sensor_loop, args=(client,), daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5002)
