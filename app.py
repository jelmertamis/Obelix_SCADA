# app.py
import sqlite3
from flask import Flask
from flask_socketio import SocketIO
from obelix.config import Config
from obelix.database import init_db
from obelix.sensor_database import init_sensor_db

# Initialiseer databases vóór andere imports
init_db()
init_sensor_db()

# Nu andere imports
from obelix.modbus_client import init_modbus
from obelix.routes import init_routes
from obelix.routes_dummy import dummy_bp      # <-- import dummy blueprint
from obelix.socketio_events import init_socketio
from obelix.sensor_monitor import start_sensor_monitor
from obelix.auto_control import start_sbr_controller

app = Flask(__name__, static_folder='static')
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

if __name__ == '__main__':
    init_modbus()
    init_routes(app)                           # bestaande routes
    app.register_blueprint(dummy_bp)           # registratie dummy-pagina
    init_socketio(socketio)
    socketio.start_background_task(start_sensor_monitor, socketio)
    start_sbr_controller(socketio)
    socketio.run(
        app,
        host='0.0.0.0',
        port=5001,
        debug=True,
        use_reloader=False
    )
