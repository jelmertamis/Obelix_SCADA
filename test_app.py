# test_app_modbus.py
# Eenvoudige testapp voor Modbus-ANSI sensoren (EX04AIS) uitlezen via seriële poort

import time
from pymodbus.client.sync import ModbusSerialClient as ModbusClient
import logging

# Logging instellen om Modbus-communicatie te zien
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

# Configuratie Modbus-serial
PORT = '/dev/ttyUSB0'      # Pas aan naar jouw poort, bijv. 'COM3' op Windows
BAUDRATE = 19200           # Baudrate van je Modbus-module
PARITY = 'N'               # Pariteit: N=none, E=even, O=odd
STOPBITS = 1               # Stopbits
BYTESIZE = 8               # Databits
TIMEOUT = 1                # Timeout in seconden

# Slave IDs en aantal kanalen per module
SLAVE_UNITS = [5, 6, 7, 8]  # EX04AIS units
CHANNELS_PER_UNIT = 4       # aantal analoge ingangen per unit

def main():
    # Maak Modbus client aan
    client = ModbusClient(
        method='rtu',
        port=PORT,
        baudrate=BAUDRATE,
        parity=PARITY,
        stopbits=STOPBITS,
        bytesize=BYTESIZE,
        timeout=TIMEOUT
    )
    if not client.connect():
        log.error(f"Kan Modbus-poort {PORT} niet openen.")
        return
    log.info(f"Verbonden met Modbus op {PORT} (baud={BAUDRATE})")

    try:
        while True:
            for slave_id in SLAVE_UNITS:
                for ch in range(CHANNELS_PER_UNIT):
                    # EX04AIS gebruikt function code 4 (input registers)
                    result = client.read_input_registers(address=ch, count=1, unit=slave_id)
                    if result.isError():
                        log.warning(f"Fout bij lezen slave {slave_id} ch{ch}: {result}")
                        continue
                    raw = result.registers[0]
                    # Simpele kalibratie, vervang door jouw eigen functie
                    scale = 1.0
                    offset = 0.0
                    value = raw * scale + offset
                    print(f"Slave {slave_id} Ch{ch}: raw={raw}  value={value}")
            print('-' * 40)
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stoppen op gebruikersverzoek.")
    finally:
        client.close()
        log.info("Modbus client gesloten.")

if __name__ == '__main__':
    main()
