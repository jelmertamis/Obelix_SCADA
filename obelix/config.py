# obelix/config.py
class Config:
    RS485_PORT = '/dev/ttyUSB0'
    BAUDRATE = 9600
    PARITY = 'E'
    STOPBITS = 1
    BYTESIZE = 8
    TIMEOUT = 1

    DB_FILE = 'settings.db'
    SENSOR_DB_FILE = 'sensor_data.db'
    TEMPLATES_AUTO_RELOAD = True

    # Polling intervals (in seconden)
    LIVE_POLL_INTERVAL = 1     # frequentie voor live-websocket updates
    STORAGE_INTERVAL = 10      # interval voor wegschrijven van gemiddelde waardes

    UNITS = [
        {'slave_id': 1, 'name': 'Relay Module 1', 'type': 'relay'},
        {'slave_id': 2, 'name': 'Relay Module 2', 'type': 'relay'},
        {'slave_id': 3, 'name': 'Relay Module 3', 'type': 'relay'},
        {'slave_id': 4, 'name': 'Relay Module 4', 'type': 'relay'},
        {'slave_id': 5, 'name': 'Analog Input 1', 'type': 'analog'},
        {'slave_id': 6, 'name': 'Analog Input 2', 'type': 'analog'},
        {'slave_id': 7, 'name': 'Analog Input 3', 'type': 'analog'},
        {'slave_id': 8, 'name': 'Analog Input 4', 'type': 'analog'},
        {'slave_id': 9, 'name': 'EX1608DD', 'type': 'relay'},
        {'slave_id': 10, 'name': 'EX04AIO', 'type': 'aio'},
    ]
    AIO_IDX = next(i for i, u in enumerate(UNITS) if u['type'] == 'aio')
    MAX_LOG = 20
    DEFAULT_PUMP_MODE = 'AUTO'
    DEFAULT_COMPRESSOR_MODE = 'OFF'