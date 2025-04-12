import time
import lgpio
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
h = None
relay_pins = [17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
compressor_speeds = [0, 0]  # K301, K302 (0-100%)
pump_modes = ["MANUAL_OFF", "MANUAL_OFF", "MANUAL_OFF"]  # P301, P303A, P406
compressor_modes = ["MANUAL_OFF", "MANUAL_OFF"]  # K301, K302

def init_gpio():
    global h
    h = lgpio.gpiochip_open(4)
    for pin in relay_pins:
        lgpio.gpio_claim_output(h, pin)

def read_sensors():
    return [0] * 10  # Dummy data

def set_relay(relay_id, state):
    lgpio.gpio_write(h, relay_pins[relay_id], state)

def set_compressor_speed(compressor_id, speed):
    compressor_speeds[compressor_id] = max(0, min(100, speed))  # Beperk tot 0-100%

def update_pump_state(pump_id):
    if pump_modes[pump_id] == "MANUAL_ON":
        set_relay(pump_id, 1)
    elif pump_modes[pump_id] == "MANUAL_OFF":
        set_relay(pump_id, 0)
    # AUTO: Later logica toevoegen (bijv. gebaseerd op sensoren)

def update_compressor_state(compressor_id):
    if compressor_modes[compressor_id] == "MANUAL_ON":
        set_compressor_speed(compressor_id, 100)  # Volle snelheid
    elif compressor_modes[compressor_id] == "MANUAL_OFF":
        set_compressor_speed(compressor_id, 0)
    # AUTO: Later logica toevoegen

@app.route('/')
def index():
    if h is None:
        init_gpio()
    values = read_sensors()
    relay_states = [lgpio.gpio_read(h, pin) for pin in relay_pins]
    return render_template('index.html', sensors=values, relays=relay_states, compressor_speeds=compressor_speeds,
                          pump_modes=pump_modes, compressor_modes=compressor_modes)

@app.route('/set_pump/<int:pump_id>/<mode>')
def set_pump(pump_id, mode):
    if h is None:
        init_gpio()
    if pump_id in [0, 1, 2]:  # P301, P303A, P406
        pump_modes[pump_id] = mode
        update_pump_state(pump_id)
    return redirect(url_for('index'))

@app.route('/set_compressor/<int:compressor_id>/<mode>')
def set_compressor(compressor_id, mode):
    if compressor_id in [0, 1]:  # K301, K302
        compressor_modes[compressor_id] = mode
        update_compressor_state(compressor_id)
    return redirect(url_for('index'))

@app.route('/set_compressor_speed_value/<int:compressor_id>', methods=['POST'])
def set_compressor_speed_value(compressor_id):
    if compressor_id in [0, 1]:  # K301, K302
        speed = int(request.form.get('speed', 0))
        set_compressor_speed(compressor_id, speed)
        compressor_modes[compressor_id] = "MANUAL_ON"  # Speed instellen zet modus naar MANUAL_ON
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_gpio()
    app.run(host='0.0.0.0', port=5000)
