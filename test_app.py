# test_app.py
import time
import minimalmodbus
import serial
import logging
import sqlite3

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
RS485_PORT = '/dev/ttyUSB0'       # Pas aan: bijv. 'COM3' op Windows of het juiste /dev/…
BAUDRATE   = 9600
PARITY     = serial.PARITY_EVEN
STOPBITS   = 1
BYTESIZE   = 8
TIMEOUT    = 1                     # in seconden

# ─── Sensor-units ──────────────────────────────────────────────────────────
ANALOG_UNITS = [
    {'slave_id': 5, 'name': 'Analog Input 1'},
    {'slave_id': 6, 'name': 'Analog Input 2'},
    {'slave_id': 7, 'name': 'Analog Input 3'},
    {'slave_id': 8, 'name': 'Analog Input 4'},
]
CHANNELS_PER_UNIT = 4              # 4 analoge ingangen per module

def init_modbus_clients():
    clients = []
    for idx, u in enumerate(ANALOG_UNITS):
        inst = minimalmodbus.Instrument(RS485_PORT, u['slave_id'], mode=minimalmodbus.MODE_RTU)
        inst.serial.baudrate   = BAUDRATE
        inst.serial.parity     = PARITY
        inst.serial.stopbits   = STOPBITS
        inst.serial.bytesize   = BYTESIZE
        inst.serial.timeout    = TIMEOUT
        inst.clear_buffers_before_each_transaction = True
        inst.debug = False  # op True voor RTU-traces

        try:
            # test-read: input-register 0 (functioncode 4)
            inst.read_register(0, functioncode=4)
            log.info(f"✔ Modbus OK voor {u['name']} (ID {u['slave_id']})")
        except Exception as e:
            log.error(f"✖ Fout init {u['name']} (ID {u['slave_id']}): {e}")
        clients.append(inst)
    return clients

def sensor_monitor(clients):
    while True:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[{timestamp}] Uitlezing analoge sensoren:")
        for idx, (u, inst) in enumerate(zip(ANALOG_UNITS, clients)):
            for ch in range(CHANNELS_PER_UNIT):
                try:
                    raw = inst.read_register(
                        registeraddress=ch,
                        number_of_decimals=0,
                        functioncode=4
                    )
                    cal = get_calibration(idx, ch)
                    val = raw * cal['scale'] + cal['offset']
                    print(f"  {u['name']} (ID {u['slave_id']}) Ch{ch}: raw={raw:5d}  value={val:8.2f}")
                except Exception as e:
                    log.warning(f"  Fout bij {u['name']} Ch{ch}: {e}")
        print('-' * 40)
        time.sleep(1)

if __name__ == '__main__':
    clients = init_modbus_clients()
    sensor_monitor(clients)
