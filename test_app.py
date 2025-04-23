# test_app_modbus_minimal.py
# Eenvoudige testapp voor EX04AIS sensoren uitlezen met MinimalModbus

import time
import minimalmodbus
import logging
import serial

# Logging om te zien wat MinimalModbus doet
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Seriële poort-configuratie (pas PORT aan naar jouw systeem, bijv. 'COM3')
PORT = '/dev/ttyUSB0'
BAUDRATE = 19200           # Baudrate van je Modbus-module
PARITY   = serial.PARITY_NONE  # Geen pariteit
STOPBITS = 1
BYTESIZE = 8
TIMEOUT  = 1               # Timeout in seconden

# Welke slave IDs en hoeveel kanalen per module
SLAVE_UNITS = [5, 6, 7, 8]
CHANNELS_PER_UNIT = 4

def main():
    # Maak voor elke slave een MinimalModbus Instrument
    instruments = {}
    for sid in SLAVE_UNITS:
        inst = minimalmodbus.Instrument(PORT, sid)
        inst.serial.baudrate   = BAUDRATE
        inst.serial.parity     = PARITY
        inst.serial.stopbits   = STOPBITS
        inst.serial.bytesize   = BYTESIZE
        inst.serial.timeout    = TIMEOUT
        inst.mode              = minimalmodbus.MODE_RTU
        instruments[sid] = inst
        log.info(f"Instrument aangemaakt voor slave {sid} op {PORT}")
    
    try:
        while True:
            for sid, inst in instruments.items():
                for ch in range(CHANNELS_PER_UNIT):
                    try:
                        # Lees input-register (function code 4), geen decimalen
                        raw = inst.read_input_register(registeraddress=ch,
                                                       number_of_decimals=0,
                                                       functioncode=4)
                        # Kalibreer (pas scale/offset aan naar jouw situatie)
                        scale = 1.0
                        offset = 0.0
                        value = raw * scale + offset
                        print(f"Slave {sid} Ch{ch}: raw={raw}  value={value}")
                    except Exception as e:
                        log.warning(f"Fout bij lezen slave {sid} ch{ch}: {e}")
            print('-' * 40)
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stoppen op gebruikersverzoek.")
    finally:
        log.info("Klaar, sluit applicatie.")

if __name__ == '__main__':
    main()
