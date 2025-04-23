# test_app_ws.py
import time
import threading
import logging
import serial
import sqlite3

import minimalmodbus
from flask import Flask, render_template_string
from flask_socketio import SocketIO

# ─── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Database (voor kalibratie) ────────────────────────────────────────────
DB_FILE = 'settings.db'

def get_calibration(unit_index, channel):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      SELECT scale, offset
      FROM calibration
      WHERE unit_index=? AND channel=?
    ''', (unit_index, channel))
    row = c.fetchone()
    conn.close()
    if row:
        return {'scale': row[0], 'offset': row[1]}
    return {'scale': 1.0, 'offset': 0.0}

# ─── Modbus-configuratie ───────────────────────────────────────────────────
RS485_PORT = '/dev/ttyUSB0'    # Pas aan naar je poort
BAUDRATE   = 9600
PARITY     = serial.PARITY_EVEN
STOPBITS   = 1
BYTESIZE   = 8
TIMEOUT    = 1                # seconden

# ─── We lezen alleen slave ID 5 ────────────────────────────────────────────
SLAVE_ID = 5
CHANNELS = 4

def init_client():
    inst = minimalmodbus.Instrument(RS485_PORT, SLAVE_ID, mode=minimalmodbus.MODE_RTU)
    inst.serial.baudrate   = BAUDRATE
    inst.serial.parity     = PARITY
    inst.serial.stopbits   = STOPBITS
    inst.serial.bytesize   = BYTESIZE
    inst.serial.timeout    = TIMEOUT
    inst.clear_buffers_before_each_transaction = True
    inst.debug = False  # op True voor RTU-frames
    # test-read
    try:
        inst.read_register(0, functioncode=4)
        log.info(f"✔ Modbus OK voor slave {SLAVE_ID}")
    except Exception as e:
        log.error(f"✖ Kan slave {SLAVE_ID} niet bereiken: {e}")
    return inst

# ─── Flask + SocketIO setup ────────────────────────────────────────────────
app      = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <title>Sensor WebSocket Test</title>
</head>
<body>
  <h1>Live sensorwaarde (slave 5)</h1>
  <pre id="output">Wachten…</pre>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
  <script>
    const out = document.getElementById('output');
    const socket = io();

    socket.on('connect', () => {
      console.log('✅ WebSocket verbonden');
    });
    socket.on('sensor_update', data => {
      console.log('🔔 sensor_update:', data);
      out.textContent = 
        `Ch${data.channel}: raw=${data.raw}  value=${data.value.toFixed(2)}`;
    });
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

def sensor_loop(inst):
    """Lees elke 2s slave 5 uit en emit via WS."""
    while True:
        try:
            for ch in range(CHANNELS):
                raw = inst.read_register(ch, functioncode=4)
                cal = get_calibration(0, ch)
                val = raw * cal['scale'] + cal['offset']
                # zend per kanaal een event
                socketio.emit('sensor_update', {
                  'channel': ch,
                  'raw':      raw,
                  'value':    val
                })
                time.sleep(0.1)  # kleine pauze tussen kanalen
        except Exception as e:
            log.warning(f"Fout in uitlees-loop: {e}")
        time.sleep(2)  # wacht 2s voor de volgende ronde

if __name__ == '__main__':
    client = init_client()
    # start de achtergrond-thread
    threading.Thread(target=sensor_loop, args=(client,), daemon=True).start()
    # run op poort 5002
    socketio.run(app, host='0.0.0.0', port=5002)
