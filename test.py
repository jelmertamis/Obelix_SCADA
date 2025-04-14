import time
from flask import Flask, render_template, redirect, url_for, request
import minimalmodbus

app = Flask(__name__)

# ----------------------------
# Configuratie
# ----------------------------
RS485_PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
MODBUS_UNIT = 1
COIL_ADDRESS = 0

# Globale variabelen voor coil nummer en log berichten
current_coil = COIL_ADDRESS
log_messages = []
MAX_LOG_MESSAGES = 20

# ----------------------------
# Helper functie voor logging
# ----------------------------
def add_log(message):
    global log_messages
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG_MESSAGES:
        log_messages = log_messages[-MAX_LOG_MESSAGES:]
    print(entry)

# ----------------------------
# Modbus client setup
# ----------------------------
try:
    client = minimalmodbus.Instrument(
        port=RS485_PORT,
        slaveaddress=MODBUS_UNIT,
        mode='rtu'
    )
    client.serial.baudrate = BAUDRATE
    client.serial.parity = minimalmodbus.serial.PARITY_EVEN
    client.serial.stopbits = 1
    client.serial.bytesize = 8
    client.serial.timeout = 3
except Exception as e:
    print(f"[{time.strftime('%H:%M:%S')}] Fout bij het instellen van de client: {e}")
    exit(1)

fallback_mode = False

def init_modbus():
    global fallback_mode
    # minimalmodbus heeft geen expliciete connect-methode, maar we kunnen een test doen
    try:
        client.read_bit(COIL_ADDRESS, functioncode=1)
        add_log("Modbus RTU-verbinding tot stand gebracht.")
        fallback_mode = False
        return True
    except Exception as e:
        add_log(f"Fout bij verbinden met de RS485-stick: {e}. Fallback modus wordt geactiveerd.")
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
            add_log(f"Proberen relay {current_coil} op {state} te zetten...")
            client.write_bit(current_coil, state, functioncode=5)
            add_log(f"Relay {current_coil} succesvol op {state} gezet.")
            return True
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
            add_log(f"Proberen huidige status van relay {current_coil} te lezen...")
            current_state = client.read_bit(current_coil, functioncode=1)
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
            add_log(f"Proberen status van coil {current_coil} te lezen...")
            status = client.read_bit(current_coil, functioncode=1)
            add_log(f"Coil {current_coil} status: {'ON' if status else 'OFF'}")
            return "ON" if status else "OFF"
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
    time.sleep(1)
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

if __name__ == "__main__":
    init_modbus()
    app.run(host='0.0.0.0', port=5001)