from flask import Flask
from flask_socketio import SocketIO

from obelix.config import Config
from obelix.database import init_db
from obelix.sensor_database import init_sensor_db
from obelix.modbus_client import init_modbus
from obelix.routes import init_routes
from obelix.socketio_events import init_socketio
from obelix.sensor_monitor import start_sensor_monitor

app = Flask(__name__, static_folder='static')
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

if __name__ == '__main__':
    init_db()           # settings/calibration/relay_states
    init_sensor_db()    # sensor_data.db
    init_modbus()
    init_routes(app)
    init_socketio(socketio)
    socketio.start_background_task(start_sensor_monitor, socketio)
    socketio.run(app, host='0.0.0.0', port=5001,
                 debug=False, use_reloader=False)
