import time
from flask import Flask, render_template, redirect, url_for, request
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

app = Flask(__name__)

# ----------------------------
# Configuratie
# ----------------------------
RS485_PORT = '/dev/ttyUSB0'  # Pas aan indien nodig (bijv. "COM3" op Windows)
BAUDRATE = 9600
MODBUS_UNIT = 1             # Dit moet overeenkomen met het slave-adres van je relay unit
# Dit is het standaard coil-adres dat getest wordt
COIL_ADDRESS = 0            

# Globale variabelen voor coil nummer en log berichten
current_coil = COIL_ADDRESS  # Start met het standaard coil-adres
log_messages = []            # Lijst om logmeldingen op te slaan
MAX_LOG_MESSAGES = 20        # Maximum aantal logregels om te bewaren

# ----------------------------
# Helper functie voor logging
# ----------------------------
def add_log(message):
    global log_messages
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    log_messages.append(entry)
    # Houd enkel de laatste MAX_LOG_MESSAGES meldingen
    if len(log_messages) > MAX_LOG_MESSAGES:
        log_messages = log_messages[-MAX_LOG_MESSAGES:]
    print(entry)

# ----------------------------
# Modbus client setup
# ----------------------------
client = ModbusSerialClient(
    port=RS485_PORT,
    baudrate=BAUDRATE,
    timeout=1,
    parity='N',
    stopbits=1,
    bytesize=8
)
# Stel het standaard slave-adres in op het client-object
client.unit = MODBUS_UNIT

fallback_mode = False

def init_modbus():
    global fallback_mode
    if client.connect():
        add_log("Modbus RTU-verbinding tot stand gebracht.")
        fallback_mode = False
        return True
    else:
        add_log("Fout bij verbinden met de RS485-stick. Fallback modus wordt geactiveerd.")
        fallback_mode = True
        return False

# ----------------------------
# Modbus functies voor relay besturing
# ----------------------------
def set_relay_state(state):
    global current_coil
    if fallback_mode:
        add_log(f"[FALLBACK] Simuleer: relay {current_coil} op {state} gezet.")
        return None
    else:
        try:
            # Roep write_coil aan zonder extra keyword; het slave-adres is al ingesteld
            result = client.write_coil(current_coil, state)
            if result.isError():
                add_log(f"Fout bij instellen van relay {current_coil} op {state}.")
            else:
                add_log(f"Relay {current_coil} succesvol op {state} gezet.")
            return result
        except Exception as e:
            add_log(f"Exception in set_relay_state: {e}")
            return None

def toggle_relay():
    global current_coil
    if fallback_mode:
        add_log("[FALLBACK] Toggling relay gesimuleerd.")
        return None
    else:
        try:
            result = client.read_coils(current_coil, 1)
            if result.isError():
                add_log("Fout bij het uitlezen van de huidige relay-status.")
                return None
            current_state = result.bits[0]
            new_state = not current_state
            add_log(f"Relay {current_coil} schakelen van {current_state} naar {new_state}.")
            set_relay_state(new_state)
        except Exception as e:
            add_log(f"Exception in toggle_relay: {e}")

def get_coil_status():
    global current_coil
    if fallback_mode:
        return "Unknown (fallback mode)"
    else:
        try:
            result = client.read_coils(current_coil, 1)
            if result.isError():
                return "Error"
            else:
                return "ON" if result.bits[0] else "OFF"
        except Exception as e:
            add_log(f"Exception in get_coil_status: {e}")
            return "Exception"

# ----------------------------
# Flask Routes
# ----------------------------
@app.route('/')
def index():
    coil_state = get_coil_status()
    return render_template('test_relay_extra.html',
                           fallback_mode=fallback_mode,
                           coil_state=coil_state,
                           coil_number=current_coil,
                           log_messages=log_messages)

@app.route('/relay/<action>')
def relay_action(action):
    if action == 'on':
        set_relay_state(True)
    elif action == 'off':
        set_relay_state(False)
    elif action == 'toggle':
        toggle_relay()
    else:
        add_log(f"Ongeldige actie: {action}")
    time.sleep(1)  # Even wachten zodat de actie zichtbaar is
    return redirect(url_for('index'))

@app.route('/update_coil', methods=['POST'])
def update_coil():
    global current_coil
    try:
        new_coil = int(request.form.get('coil_number'))
        add_log(f"Update coil nummer: {new_coil}")
        current_coil = new_coil
    except Exception as e:
        add_log(f"Exception in update_coil: {e}")
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_modbus()
    app.run(host='0.0.0.0', port=5001)
