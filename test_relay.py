import time
from flask import Flask, render_template, redirect, url_for
from pymodbus.client import ModbusSerialClient

app = Flask(__name__)

# Configuratie voor de RS485 Modbus-verbinding
RS485_PORT = '/dev/ttyUSB0'  # Pas dit aan indien nodig (bijv. "COM3" op Windows)
BAUDRATE = 9600
MODBUS_UNIT = 1             # Zorg dat dit overeenkomt met de slave-ID op de relay unit
COIL_ADDRESS = 0            # Gebruik hier het coil-adres van de relay die je wilt testen

# Maak de ModbusSerialClient aan (PyModbus 3.x, zonder 'method'-parameter)
client = ModbusSerialClient(
    port=RS485_PORT,
    baudrate=BAUDRATE,
    timeout=1,
    parity='N',
    stopbits=1,
    bytesize=8
)

# Globale fallback-modus flag
fallback_mode = False

def init_modbus():
    """
    Probeer de Modbus-verbinding tot stand te brengen.
    Als dit niet lukt, wordt fallback_mode automatisch ingeschakeld.
    """
    global fallback_mode
    if client.connect():
        print("Modbus RTU-verbinding tot stand gebracht.")
        fallback_mode = False
        return True
    else:
        print("Fout bij verbinden met de RS485-stick. Fallback modus wordt geactiveerd.")
        fallback_mode = True
        return False

def set_relay_state(state):
    """
    Zet de relay op 'state' (True voor aan, False voor uit).
    Indien fallback_mode actief is, wordt de actie gesimuleerd.
    """
    if fallback_mode:
        print(f"[FALLBACK] Simuleer: relay {COIL_ADDRESS} op {state} gezet.")
        return None
    else:
        result = client.write_coil(COIL_ADDRESS, state, slave=MODBUS_UNIT)
        if result.isError():
            print(f"Fout bij het instellen van relay {COIL_ADDRESS} op {state}.")
        else:
            print(f"Relay {COIL_ADDRESS} succesvol op {state} gezet.")
        return result

def toggle_relay():
    """
    Lees de huidige relay-status en schakelt deze.
    Als fallback_mode actief is, wordt de toggle gesimuleerd.
    """
    if fallback_mode:
        print("[FALLBACK] Toggling relay gesimuleerd.")
        return None
    else:
        result = client.read_coils(COIL_ADDRESS, 1, slave=MODBUS_UNIT)
        if result.isError():
            print("Fout bij het uitlezen van de huidige relay-status.")
            return None
        current_state = result.bits[0]
        new_state = not current_state
        print(f"Relay {COIL_ADDRESS} schakelen van {current_state} naar {new_state}.")
        set_relay_state(new_state)

@app.route('/')
def index():
    """Render de testpagina."""
    return render_template('test_relay.html', fallback_mode=fallback_mode)

@app.route('/relay/<action>')
def relay_action(action):
    """
    Verwerkt de actie: 'on', 'off' of 'toggle' voor de relay.
    Na de actie wacht het even, zodat deze zichtbaar kan zijn.
    """
    if action == 'on':
        set_relay_state(True)
    elif action == 'off':
        set_relay_state(False)
    elif action == 'toggle':
        toggle_relay()
    else:
        print(f"Ongeldige actie: {action}")
    time.sleep(1)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_modbus()
    app.run(host='0.0.0.0', port=5001)
