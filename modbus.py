from flask import Flask, render_template, request, redirect, url_for
from pymodbus.client import ModbusSerialClient

app = Flask(__name__)

# Configuratie voor de RS485 Modbus-verbinding
RS485_PORT = '/dev/ttyUSB0'    # Pas dit aan indien nodig (bij Windows bijvoorbeeld "COM3")
BAUDRATE = 9600
MODBUS_UNIT = 1

# Voorbeeldadressen (pas deze aan op basis van de documentatie van je Overdigit I/O-units)
PUMP_RELAY_START_ADDRESS = 0         # Bijvoorbeeld adressen 0, 1, 2, ... voor de pompen
COMPRESSOR_RELAY_START_ADDRESS = 10    # Bijvoorbeeld adressen 10, 11 voor de compressors

# Globale toestanden voor de apparaten
pump_modes = ["MANUAL_OFF", "MANUAL_OFF", "MANUAL_OFF"]       # Voor P301, P303A, P406
compressor_modes = ["MANUAL_OFF", "MANUAL_OFF"]                 # Voor K301, K302
compressor_speeds = [0, 0]                                      # Snelheidswaardes voor K301 en K302 (bijv. 0 t/m 100)

# Flag voor fallback modus: als de Modbus-verbinding niet lukt, activeren we simulatiemodus
fallback_mode = False

# Maak de ModbusSerialClient (PyModbus 3.x: zonder 'method'-parameter)
client = ModbusSerialClient(
    port=RS485_PORT,
    baudrate=BAUDRATE,
    timeout=1,
    parity='N',      # 'N' voor geen parity (pas aan indien nodig)
    stopbits=1,      # Aantal stopbits
    bytesize=8       # Aantal databits
)

def init_modbus():
    """
    Probeer de Modbus-verbinding tot stand te brengen.
    Als dit niet lukt, activeer de fallback-modus zodat we de logica en webinterface kunnen testen zonder hardware.
    """
    global fallback_mode
    connection = client.connect()
    if connection:
        print("Modbus RTU-verbinding tot stand gebracht.")
        fallback_mode = False
        return True
    else:
        print("Fout bij verbinden met de RS485-stick. Fallback modus wordt geactiveerd.")
        fallback_mode = True
        return False

def set_relay_modbus(coil_address, state):
    """
    Stuur een relay-opdracht via Modbus (of simuleer deze in fallback modus).

    :param coil_address: Het coil-adres (bijv. PUMP_RELAY_START_ADDRESS + pump_id).
    :param state: True voor aan, False voor uit.
    """
    if fallback_mode:
        print(f"[FALLBACK] Simuleer coil {coil_address} op {state}")
        return None
    else:
        # Gebruik 'slave' in plaats van 'unit'
        result = client.write_coil(coil_address, state, slave=MODBUS_UNIT)
        if result.isError():
            print(f"Fout bij het schrijven naar coil {coil_address}")
        else:
            print(f"Coil {coil_address} succesvol geschreven naar {state}")
        return result

def update_pump_state(pump_id):
    """
    Update de staat van een pomp relay op basis van de ingestelde modus.
    """
    coil_address = PUMP_RELAY_START_ADDRESS + pump_id
    if pump_modes[pump_id] == "MANUAL_ON":
        set_relay_modbus(coil_address, True)
    else:
        set_relay_modbus(coil_address, False)

def update_compressor_state(compressor_id):
    """
    Update de staat van een compressor relay op basis van de ingestelde modus.
    Tevens past deze functie de globale compressor_speeds aan.
    """
    coil_address = COMPRESSOR_RELAY_START_ADDRESS + compressor_id
    global compressor_speeds
    if compressor_modes[compressor_id] == "MANUAL_ON":
        set_relay_modbus(coil_address, True)
        compressor_speeds[compressor_id] = 100  # Bijvoorbeeld volledige snelheid
    else:
        set_relay_modbus(coil_address, False)
        compressor_speeds[compressor_id] = 0

def read_sensors():
    """
    Dummy functie voor het uitlezen van sensorgegevens.
    Pas deze functie later aan als je sensoren via Modbus of een ander protocol wilt uitlezen.
    """
    return [0] * 10

@app.route('/')
def index():
    sensors = read_sensors()
    # Simuleer de relay-staten op basis van pump_modes: aangenomen dat de eerste 3 coils voor de pompen worden gebruikt.
    relay_states = [False] * 10
    for i, mode in enumerate(pump_modes):
        if mode == "MANUAL_ON":
            relay_states[i] = True

    return render_template('index.html',
                           sensors=sensors,
                           relays=relay_states,
                           pump_modes=pump_modes,
                           compressor_modes=compressor_modes,
                           compressor_speeds=compressor_speeds,
                           fallback_mode=fallback_mode)

@app.route('/set_pump/<int:pump_id>/<mode>')
def set_pump(pump_id, mode):
    if pump_id in range(len(pump_modes)):
        pump_modes[pump_id] = mode
        update_pump_state(pump_id)
    return redirect(url_for('index'))

@app.route('/set_compressor/<int:compressor_id>/<mode>')
def set_compressor(compressor_id, mode):
    if compressor_id in range(len(compressor_modes)):
        compressor_modes[compressor_id] = mode
        update_compressor_state(compressor_id)
    return redirect(url_for('index'))

@app.route('/set_compressor_speed_value/<int:compressor_id>', methods=['POST'])
def set_compressor_speed_value(compressor_id):
    if compressor_id in range(len(compressor_modes)):
        speed = int(request.form.get('speed', 0))
        # Hier kun je een Modbus-register write doen als de hardware ondersteuning heeft voor snelheidsaanpassing.
        print(f"Stel snelheid in voor compressor {compressor_id}: {speed}%")
        compressor_speeds[compressor_id] = max(0, min(100, speed))
        compressor_modes[compressor_id] = "MANUAL_ON"
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_modbus()
    app.run(host='0.0.0.0', port=5000)
