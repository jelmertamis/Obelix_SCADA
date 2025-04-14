import time
from pymodbus.client import ModbusSerialClient

# Configuratie
PORT = '/dev/ttyUSB0'  # Pas aan als nodig (bijv. "COM3" op Windows)
BAUDRATE = 9600
SLAVE_ID = 1           # Modbus slave-adres
COIL_ADDRESS = 0       # Coil om te testen
TIMEOUT = 3            # Timeout in seconden

# Stel Modbus client in
client = ModbusSerialClient(
    port=PORT,
    baudrate=BAUDRATE,
    timeout=TIMEOUT,
    parity='N',
    stopbits=1,
    bytesize=8
)

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_modbus(use_unit=True):
    keyword = "unit" if use_unit else "slave"
    log(f"Testen met keyword: {keyword}")
    
    # Probeer verbinding te maken
    if not client.connect():
        log("Kan niet verbinden met Modbus device. Controleer poort en hardware.")
        return
    
    log("Verbonden met Modbus device!")
    
    try:
        # Lees coil 0
        log(f"Proberen coil {COIL_ADDRESS} te lezen...")
        kwargs = {keyword: SLAVE_ID}
        result = client.read_coils(COIL_ADDRESS, 1, **kwargs)
        if result.isError():
            log("Fout bij het lezen van coil: Modbus fout")
        else:
            status = "ON" if result.bits[0] else "OFF"
            log(f"Coil {COIL_ADDRESS} status: {status}")
        
        # Schrijf coil 0 naar True (aan)
        log(f"Proberen coil {COIL_ADDRESS} op True (aan) te zetten...")
        result = client.write_coil(COIL_ADDRESS, True, **kwargs)
        if result.isError():
            log("Fout bij het schrijven van coil: Modbus fout")
        else:
            log(f"Coil {COIL_ADDRESS} succesvol op True gezet")
        
        # Wacht even
        time.sleep(1)
        
        # Schrijf coil 0 naar False (uit)
        log(f"Proberen coil {COIL_ADDRESS} op False (uit) te zetten...")
        result = client.write_coil(COIL_ADDRESS, False, **kwargs)
        if result.isError():
            log("Fout bij het schrijven van coil: Modbus fout")
        else:
            log(f"Coil {COIL_ADDRESS} succesvol op False gezet")
    
    except Exception as e:
        log(f"Exception: {str(e)}")
    
    finally:
        client.close()
        log("Verbinding gesloten.")

if __name__ == "__main__":
    log("Start Modbus test...")
    # Probeer eerst met 'unit' (correct voor pymodbus 3.9.1)
    test_modbus(use_unit=True)
    
    # Als je wilt testen met 'slave' (voor het geval 'unit' faalt), haal onderstaande commentaar weg
    log("\nHerhalen met 'slave' keyword...")
    test_modbus(use_unit=False)