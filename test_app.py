# read_sensors.py
import time
import minimalmodbus
import serial
import logging

# Logging aanzetten (optioneel)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Seriële poort-configuratie
PORT      = '/dev/ttyUSB0'           # of 'COM3' op Windows
BAUDRATE  = 19200
PARITY    = serial.PARITY_NONE
STOPBITS  = 1
BYTESIZE  = 8
TIMEOUT   = 1                        # seconde

# Welke slave IDs en kanalen
SLAVE_UNITS         = [5, 6, 7, 8]   # jouw EX04AIS units
CHANNELS_PER_UNIT   = 4              # 4 ingangen per module

def main():
    # Maak per slave een instrument
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
        log.info(f"Instrument voor slave {sid} klaar op {PORT}")

    try:
        while True:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{timestamp}] Lees sensoren:")
            for sid, inst in instruments.items():
                for ch in range(CHANNELS_PER_UNIT):
                    try:
                        # lees input-register (function code 4)
                        raw = inst.read_register(
                            registeraddress=ch,
                            number_of_decimals=0,
                            functioncode=4
                        )
                        # eenvoudige kalibratie (pas aan naar behoefte)
                        scale  = 1.0
                        offset = 0.0
                        value  = raw * scale + offset
                        print(f"  Slave {sid} Ch{ch}: raw={raw:5d}  value={value:.2f}")
                    except Exception as e:
                        log.warning(f"Fout bij slave {sid} ch{ch}: {e}")
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stoppen op gebruikersverzoek.")

if __name__ == '__main__':
    main()
