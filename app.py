from flask import Flask
from flask_socketio import SocketIO

from obelix.config import Config
from obelix.database import init_db
from obelix.sensor_database import init_sensor_db
from obelix.modbus_client import init_modbus
from obelix.routes import init_routes
from obelix.socketio_events import init_socketio
from obelix.sensor_monitor import start_sensor_monitor

# Maak de Flask-app en configureer
app = Flask(__name__, static_folder='static')
app.config.from_object(Config)
# Gebruik SocketIO voor real-time communicatie
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

if __name__ == '__main__':
    # Initialiseer beide databases
    init_db()           # Hoofd-database (settings, calibration, relay_states, etc.)
    init_sensor_db()    # Losse sensor-database voor historische meetwaarden

    # Initialiseer Modbus-communicatie
    init_modbus()

    # Registreer alle HTTP-routes en blueprints
    init_routes(app)

    # Zet SocketIO-events op
    init_socketio(socketio)

    # Start background task voor sensor monitoring (live update + opslag)
    socketio.start_background_task(start_sensor_monitor, socketio)

    # Start de server
    socketio.run(
        app,
        host='0.0.0.0',
        port=5001,
        debug=False,
        use_reloader=False
    )
