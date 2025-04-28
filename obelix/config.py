# obelix/config.py

class Config:
    # Serial / Modbus settings
    RS485_PORT = '/dev/ttyUSB0'
    BAUDRATE   = 9600
    PARITY     = 'E'  # minimalmodbus.serial.PARITY_EVEN
    STOPBITS   = 1
    BYTESIZE   = 8
    TIMEOUT    = 1

    # Database files
    DB_FILE         = 'settings.db'      # hoofd-database voor settings/calibratie/relay_states
    SENSOR_DB_FILE  = 'sensor_data.db'   # losse database voor historische sensordata
    TEMPLATES_AUTO_RELOAD = True

    # Polling intervals (in seconden)
    LIVE_POLL_INTERVAL  = 1    # frequentie live-update
    STORAGE_INTERVAL    = 10   # interval gemiddeld opslaan

    # Units definition
    UNITS = [
        {'slave_id': 1,  'name': 'Relay Module 1',    'type': 'relay'},
        {'slave_id': 2,  'name': 'Relay Module 2',    'type': 'relay'},
        {'slave_id': 3,  'name': 'Relay Module 3',    'type': 'relay'},
        {'slave_id': 4,  'name': 'Relay Module 4',    'type': 'relay'},
        {'slave_id': 5,  'name': 'Analog Input 1',   'type': 'analog'},
        {'slave_id': 6,  'name': 'Analog Input 2',   'type': 'analog'},
        {'slave_id': 7,  'name': 'Analog Input 3',   'type': 'analog'},
        {'slave_id': 8,  'name': 'Analog Input 4',   'type': 'analog'},
        {'slave_id': 9,  'name': 'EX1608DD',         'type': 'relay'},
        {'slave_id': 10, 'name': 'EX04AIO',          'type': 'aio'},
    ]
    AIO_IDX = next(i for i, u in enumerate(UNITS) if u['type'] == 'aio')

    # Logging
    MAX_LOG = 20

    # Default modes
    DEFAULT_PUMP_MODE       = 'AUTO'
    DEFAULT_COMPRESSOR_MODE = 'OFF'

    # R302-specific mappings
    # Relays map coil índices to meaningful labels
    R302_RELAY_MAPPING = {
        0: 'Influent Pump',
        1: 'Effluent Pump',
        2: 'Nutrient Pump',
        3: 'Compressor ON/OFF (K303)',
        4: 'Compressor ON/OFF (K304)',
        5: 'Heating Valve (A503)'
    }

    # Sensors on slave ID 5
    R302_SENSOR_MAPPING = {
        0: 'Level Sensor',
        1: 'pH',
        2: 'Temperature',
        3: 'Dissolved Oxygen'
    }

    # Analog outputs on slave ID 10
    R302_AIO_MAPPING = {
        0: 'Compressor Speed (K303)',
        1: 'Compressor Speed (K304)'
    }
