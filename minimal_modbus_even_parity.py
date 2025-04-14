import time
import minimalmodbus

# Configuratie
PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
SLAVE_ID = 1
COIL_ADDRESS = 0
TIMEOUT = 3

# Stel Modbus client in
try:
    client = minimalmodbus.Instrument(
        port=PORT,
        slaveaddress=SLAVE_ID,
        mode='rtu'
    )
    client.serial.baudrate = BAUDRATE
    client.serial.parity = minimalmodbus.serial.PARITY_EVEN  # Gewijzigd naar Even pariteit
    client.serial.stopbits = 1
    client.serial.bytesize = 8
    client.serial.timeout = TIMEOUT
except Exception as e:
    print(f"[{time.strftime('%H:%M:%S')}] Fout bij het instellen van de client: {e}")
    exit(1)

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_modbus():
    log("Start Modbus test...")
    
    try:
        # Lees coil 0
        log(f"Proberen coil {COIL_ADDRESS} te lezen...")
        coil_status = client.read_bit(COIL_ADDRESS, functioncode=1)  # Read coil
        status = "ON" if coil_status else "OFF"
        log(f"Coil {COIL_ADDRESS} status: {status}")
        
        # Schrijf coil 0 naar True (aan)
        log(f"Proberen coil {COIL_ADDRESS} op True (aan) te zetten...")
        client.write_bit(COIL_ADDRESS, True, functioncode=5)  # Write single coil
        log(f"Coil {COIL_ADDRESS} succesvol op True gezet")
        
        # Wacht even
        time.sleep(1)
        
        # Schrijf coil 0 naar False (uit)
        log(f"Proberen coil {COIL_ADDRESS} op False (uit) te zetten...")
        client.write_bit(COIL_ADDRESS, False, functioncode=5)  # Write single coil
        log(f"Coil {COIL_ADDRESS} succesvol op False gezet")
    
    except minimalmodbus.NoResponseError:
        log("Fout: Geen antwoord ontvangen van de relay unit.")
    except minimalmodbus.InvalidResponseError:
        log("Fout: Ongeldig antwoord ontvangen van de relay unit.")
    except Exception as e:
        log(f"Exception: {str(e)}")
    
    finally:
        client.serial.close()
        log("Verbinding gesloten.")

if __name__ == "__main__":
    test_modbus()