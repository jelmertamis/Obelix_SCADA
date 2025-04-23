# sensors_test_app.py
from flask import Flask, render_template_string
from flask_socketio import SocketIO
import threading, time, random

app = Flask(__name__)
socketio = SocketIO(app)

# Eenvoudige pagina met exact dezelfde HTML/JS als jouw sensors.html
PAGE = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Test Sensor Uitlezingen</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 1rem; }
    table { border-collapse: collapse; width: 100%; max-width: 600px; }
    th, td { border: 1px solid #ccc; padding: .5rem; }
    th { background: #007bff; color: #fff; }
  </style>
</head>
<body>
  <h1>Sensor Uitlezingen (Test)</h1>
  <table>
    <thead>
      <tr>
        <th>Naam</th>
        <th>Slave ID</th>
        <th>Kanaal</th>
        <th>Ruwe Waarde</th>
        <th>Gekalibreerd</th>
      </tr>
    </thead>
    <tbody id="sensorBody"></tbody>
  </table>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      console.log('➡️ Connecting to WS…');
      const socket = io();

      socket.on('connect', () => {
        console.log('✅ WS connected');
      });
      socket.on('sensor_update', readings => {
        console.log('🔔 sensor_update:', readings);
        const tbody = document.getElementById('sensorBody');
        tbody.innerHTML = '';
        readings.forEach(r => {
          const tr = document.createElement('tr');
          ['name','slave_id','channel','raw','value'].forEach(key => {
            const td = document.createElement('td');
            td.textContent = r[key];
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

def sensor_broadcast_loop():
    """Simuleer elke seconde 8 kanaalmetingen."""
    while True:
        dummy = [{
            'name':     'TestSensor',
            'slave_id': sid,
            'channel':  ch,
            'raw':      random.randint(0, 4095),
            'value':    round(random.random() * 5.0, 2)
        } for sid in (5,6,7,8) for ch in range(2)]  # bv. 4 units × 2 kanalen
        socketio.emit('sensor_update', dummy)
        time.sleep(1)

if __name__ == '__main__':
    # start de broadcast-thread
    t = threading.Thread(target=sensor_broadcast_loop, daemon=True)
    t.start()

    # run op poort 5002
    socketio.run(app, host='0.0.0.0', port=5002)
