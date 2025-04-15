import time
from flask import Flask, render_template, redirect, url_for, request
import minimalmodbus

app = Flask(__name__)

# ----------------------------
# Configuratie
# ----------------------------
RS485_PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
UNITS = [
    {'slave_id': 1, 'name': 'Unit 1'},  # Eerste unit
    {'slave_id': 2, 'name': 'Unit 2'}   # Tweede unit, pas de slave ID aan
]
COIL_ADDRESS = 0

# Globale variabelen
current_unit = 0  # Start met de eerste unit
current_coil = COIL_ADDRESS
log_messages = []
MAX_LOG_MESSAGES = 20

# ----------------------------
# Modbus clients setup
# ----------------------------
clients = []
for unit in UNITS:
    try:
        client = minimalmodbus.Instrument(
            port=RS485_PORT,
            slaveaddress=unit['slave_id'],
            mode='rtu'
        )
        client.serial.baudrate = BAUDRATE
        client.serial.parity = minimalmodbus.serial.PARITY_EVEN
        client.serial.stopbits = 1
        client.serial.bytesize = 8
        client.serial.timeout = 3
        clients.append(client)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Fout bij het instellen van client voor slave ID {unit['slave_id']}: {e}")
        exit(1)

fallback_mode = False

def init_modbus():
    global fallback_mode
    try:
        for i, client in enumerate(clients):
            client.read_bit(COIL_ADDRESS, functioncode=1)
            log(f"Modbus RTU-verbinding tot stand gebracht voor {UNITS[i]['name']} (slave ID {UNITS[i]['slave_id']}).")
        fallback_mode = False
        return True
    except Exception as e:
        log(f"Fout bij verbinden met de RS485-stick: {e}. Fallback modus wordt geactiveerd.")
        fallback_mode = True
        return False

# ----------------------------
# Helper functie voor logging
# ----------------------------
def log(message):
    global log_messages
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG_MESSAGES:
        log_messages = log_messages[-MAX_LOG_MESSAGES:]
    print(entry)

# ----------------------------
# Modbus functies voor relay besturing
# ----------------------------
def set_relay_state(state):
    global current_coil, current_unit
    if fallback_mode:
        log(f"[FALLBACK] Simuleer: relay {current_coil} op {state} gezet voor {UNITS[current_unit]['name']}.")
        return None
    else:
        try:
            client = clients[current_unit]
            log(f"Proberen relay {current_coil} op {state} te zetten voor {UNITS[current_unit]['name']}...")
            client.write_bit(current_coil, state, functioncode=5)
            log(f"Relay {current_coil} succesvol op {state} gezet voor {UNITS[current_unit]['name']}.")
            return True
        except Exception as e:
            log(f"Exception in set_relay_state: {e}")
            return None

def toggle_relay():
    global current_coil, current_unit
    if fallback_mode:
        log(f"[FALLBACK] Toggling relay gesimuleerd voor {UNITS[current_unit]['name']}.")
        return None
    else:
        try:
            client = clients[current_unit]
            log(f"Proberen huidige status van relay {current_coil} te lezen voor {UNITS[current_unit]['name']}...")
            current_state = client.read_bit(current_coil, functioncode=1)
            new_state = not current_state
            log(f"Relay {current_coil} schakelen van {current_state} naar {new_state} voor {UNITS[current_unit]['name']}.")
            set_relay_state(new_state)
        except Exception as e:
            log(f"Exception in toggle_relay: {e}")

def get_coil_status():
    global current_coil, current_unit
    if fallback_mode:
        return "Unknown (fallback mode)"
    else:
        try:
            client = clients[current_unit]
            log(f"Proberen status van coil {current_coil} te lezen voor {UNITS[current_unit]['name']}...")
            status = client.read_bit(current_coil, functioncode=1)
            log(f"Coil {current_coil} status: {'ON' if status else 'OFF'} voor {UNITS[current_unit]['name']}.")
            return "ON" if status else "OFF"
        except Exception as e:
            log(f"Exception in get_coil_status: {e}")
            return "Exception"

# ----------------------------
# Flask Routes
# ----------------------------
@app.route('/')
def index():
    coil_state = get_coil_status()
    return render_template('test_relay_two_units.html',
                           fallback_mode=fallback_mode,
                           coil_state=coil_state,
                           coil_number=current_coil,
                           current_unit=UNITS[current_unit]['name'],
                           units=UNITS,
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
        log(f"Ongeldige actie: {action}")
    time.sleep(1)
    return redirect(url_for('index'))

@app.route('/update_coil', methods=['POST'])
def update_coil():
    global current_coil
    try:
        new_coil = int(request.form.get('coil_number'))
        log(f"Update coil nummer: {new_coil}")
        current_coil = new_coil
    except Exception as e:
        log(f"Exception in update_coil: {e}")
    return redirect(url_for('index'))

@app.route('/select_unit', methods=['POST'])
def select_unit():
    global current_unit
    try:
        new_unit = int(request.form.get('unit_index'))
        log(f"Selecteer unit: {UNITS[new_unit]['name']} (slave ID {UNITS[new_unit]['slave_id']})")
        current_unit = new_unit
    except Exception as e:
        log(f"Exception in select_unit: {e}")
    return redirect(url_for('index'))

if __name__ == "__main__":
    init_modbus()
    app.run(host='0.0.0.0', port=5001)