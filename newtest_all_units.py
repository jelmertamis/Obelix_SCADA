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
    {'slave_id': 1, 'name': 'Relay Module 1', 'type': 'relay'},
    {'slave_id': 2, 'name': 'Relay Module 2', 'type': 'relay'},
    {'slave_id': 3, 'name': 'Relay Module 3', 'type': 'relay'},
    {'slave_id': 4, 'name': 'Relay Module 4', 'type': 'relay'},
    {'slave_id': 5, 'name': 'Analog Input 1', 'type': 'analog'},
    {'slave_id': 6, 'name': 'Analog Input 2', 'type': 'analog'},
    {'slave_id': 7, 'name': 'Analog Input 3', 'type': 'analog'},
    {'slave_id': 8, 'name': 'Analog Input 4', 'type': 'analog'},
    {'slave_id': 9, 'name': 'EX1608DD', 'type': 'relay'}  # EX1608DD behandelen als een relaismodule
]
COIL_ADDRESS = 0  # Voor relaismodules
INPUT_REGISTER_ADDRESS = 0  # Voor analoge inputmodules, pas aan als nodig

# Globale variabelen
current_unit = 0  # Start met de eerste unit
current_coil = COIL_ADDRESS
current_register = INPUT_REGISTER_ADDRESS
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
            if UNITS[i]['type'] == 'relay':
                client.read_bit(COIL_ADDRESS, functioncode=1)
            else:  # Analoge inputmodules
                client.read_register(INPUT_REGISTER_ADDRESS, functioncode=4)
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
# Modbus functies
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

def get_analog_value():
    global current_register, current_unit
    if fallback_mode:
        return "Unknown (fallback mode)"
    else:
        try:
            client = clients[current_unit]
            log(f"Proberen analoge waarde van register {current_register} te lezen voor {UNITS[current_unit]['name']}...")
            value = client.read_register(current_register, functioncode=4)  # Gebruik functiecode 4 voor input registers
            log(f"Analoge waarde van register {current_register}: {value} voor {UNITS[current_unit]['name']}.")
            return value
        except Exception as e:
            log(f"Exception in get_analog_value: {e}")
            return "Exception"

# ----------------------------
# Flask Routes
# ----------------------------
@app.route('/')
def index():
    if UNITS[current_unit]['type'] == 'relay':
        status = get_coil_status()
    else:
        status = get_analog_value()
    return render_template('test_all_units.html',
                           fallback_mode=fallback_mode,
                           status=status,
                           coil_number=current_coil,
                           register_number=current_register,
                           current_unit=UNITS[current_unit]['name'],
                           unit_type=UNITS[current_unit]['type'],
                           units=UNITS,
                           log_messages=log_messages)

@app.route('/relay/<action>')
def relay_action(action):
    if UNITS[current_unit]['type'] != 'relay':
        log("Actie niet mogelijk: Deze unit is geen relaismodule.")
        return redirect(url_for('index'))
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

@app.route('/update_register', methods=['POST'])
def update_register():
    global current_register
    try:
        new_register = int(request.form.get('register_number'))
        log(f"Update register nummer: {new_register}")
        current_register = new_register
    except Exception as e:
        log(f"Exception in update_register: {e}")
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

@app.route('/sensors')
def sensors():
    readings = []
    for i, unit in enumerate(UNITS):
        if unit['type'] == 'analog':
            # wissel current_unit tijdelijk om zodat de helper de juiste client pakt
            temp_unit = current_unit
            try:
                # haal de waarde op
                global current_unit, current_register
                current_unit = i
                current_register = INPUT_REGISTER_ADDRESS
                value = get_analog_value()
            finally:
                # zet current_unit weer terug
                current_unit = temp_unit
            readings.append({
                'name': unit['name'],
                'slave_id': unit['slave_id'],
                'value': value
            })
    return render_template('sensors.html', readings=readings, fallback_mode=fallback_mode)

if __name__ == "__main__":
    init_modbus()
    app.run(host='0.0.0.0', port=5001)