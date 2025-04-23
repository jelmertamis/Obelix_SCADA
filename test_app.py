# test_app.py
# Eenvoudige Flask-SocketIO app voor het testen van de sensor-pagina en WebSocket-communicatie

from flask import Flask, render_template_string
from flask_socketio import SocketIO
import threading
import time
import random

app = Flask(__name__)
socketio = SocketIO(app)

# De HTML-pagina met je sensortabel en client-side JS
PAGE = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Test SCADA Sensors</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 1rem; }
    table { border-collapse: collapse; width: 100%; max-width: 600px; }
    th, td { border: 1px solid #ccc; padding: .5rem; }
    th { background: #007bff; color: #fff; }
  </style>
</head>
<body>
  <h1>Test Sensor Uitlezingen</h1>
  <p>Deze pagina gebruikt WebSockets om sensor-data te tonen.</p>
  <table>
    <thead>
      <tr>
        <th>Naam</th><th>Slave ID</th><th>Kanaal</th><th>Ruwe Waarde</th><th>Gekalibreerd</th>
      </tr>
    </thead>
    <tbody id="sensorBody"></tbody>
  </table>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      console.log('🔌 Verbinding opzetten...');
      const socket = io();

      socket.on('connect', () => console.log('✅ Verbonden met server'));
      socket.on('sensor_update', readings => {
        console.log('🔔 sensor_update:', readings);
        const tbody = document.getElementById('sensorBody');
        tbody.innerHTML = '';
        readings.forEach(r => {
          const tr = document.createElement('tr');
          ['name','slave_id','channel','raw','value'].forEach(k => {
            const td = document.createElement('td');
            td.textContent = r[k] != null ? r[k] : '—';
            tr.appendChild(td);
          });
          tbody.appendChild(tr);
        });
      });
    });
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(PAGE)

def sensor_loop():
    """Simuleer iedere seconde wat dummy-sensorwaarden."""
    while True:
        dummy = [{
            'name':     f'DemoSensor{sid}',
            'slave_id': sid,
            'channel':  ch,
            'raw':      random.randint(0, 4095),
            'value':    round(random.random() * 10, 2)
        } for sid in (5,6,7,8) for ch in range(2)]
        socketio.emit('sensor_update', dummy)
        time.sleep(1)

if __name__ == '__main__':
    # Start de dummy sensor-thread
    threading.Thread(target=sensor_loop, daemon=True).start()
    # Run op poort 5002 om niet te conflicteren met je hoofd-app
    socketio.run(app, host='0.0.0.0', port=5002, debug=True)
