import time
from flask import Flask, render_template, redirect, url_for
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

app = Flask(__name__)

# Configuratie voor de RS485 Modbus-verbinding
RS485_PORT = '/dev/ttyUSB0'  # Pas dit aan indien nodig (bijv. "COM3" op Windows)
BAUDRATE = 9600
MODBUS_UNIT = 1             # Dit moet overeenkomen met het slave-adres van je relay unit
COIL_ADDRESS = 0            # Het coil-adres van de relay die je wilt testen

# Maak de ModbusSerialClient aan (PyModbus 3.x)
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
    Als dit niet lukt, wordt fallback_mode ingeschakeld.
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
    Indien er een fout optreedt, wordt de fout afgehandeld zodat de webpagina niet vastloopt.
    """
    if fallback_mode:
        print(f"[FALLBACK] Simuleer: relay {COIL_ADDRESS} op {state} gezet.")
        return None
    else:
        try:
            result = client.write_coil(COIL_ADDRESS, state, slave=MODBUS_UNIT)
            if result.isError():
                print(f"Fout bij het instellen van relay {COIL_ADDRESS} op {state}.")
            else:
                print(f"Relay {COIL_ADDRESS} succesvol op {state} gezet.")
            return result
        except Exception as e:
            print(f"Exception tijdens set_relay_state: {e}")
            return None

def toggle_relay():
    """
    Leest de huidige relay-status en schakelt deze.
    Indien er een fout optreedt, wordt dit netjes afgehandeld.
    """
    if fallback_mode:
        print("[FALLBACK] Toggling relay gesimuleerd.")
        return None
    else:
        try:
            result = client.read_coils(COIL_ADDRESS, 1, slave=MODBUS_UNIT)
            if result.isError():
                print("Fout bij het uitlezen van de huidige relay-status.")
                return None
            current_state = result.bits[0]
            new_state = not current_state
            print(f"Relay {COIL_ADDRESS} schakelen van {current_state} naar {new_state}.")
            set_relay_state(new_state)
        except Exception as e:
            print(f"Exception tijdens toggle: {e}")

def get_coil_status():
    """
    Leest de status van de coil (ON of OFF).
    Als fallback_mode actief is of als er een fout optreedt, retourneert het een geschikte melding.
    """
    if fallback_mode:
        return "Unknown (fallback mode)"
    else:
        try:
            result = client.read_coils(COIL_ADDRESS, 1, slave=MODBUS_UNIT)
            if result.isError():
                return "Error"
            else:
                return "ON" if result.bits[0] else "OFF"
        except Exception as e:
            print(f"Exception tijdens het lezen van de coil status: {e}")
            return "Exception"

@app.route('/')
def index():
    coil_state = get_coil_status()
    return render_template('test_relay.html',
                           fallback_mode=fallback_mode,
                           coil_state=coil_state,
                           coil_number=COIL_ADDRESS)

@app.route('/relay/<action>')
def relay_action(action):
    if action == 'on':
        set_relay_state(True)
    elif action == 'off':
        set_relay_state(False)
    elif action == 'toggle':
        toggle_relay()
    else:
        print(f"Ongeldige actie: {action}")
    time.sleep(1)  # Kort wachten zodat de actie zichtbaar is
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_modbus()
    app.run(host='0.0.0.0', port=5001)
