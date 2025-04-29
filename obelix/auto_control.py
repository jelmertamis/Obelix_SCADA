# obelix/auto_control.py

import threading
from flask_socketio import SocketIO
from obelix.config import Config
from obelix.database import get_setting, set_setting, save_relay_state, get_relay_state
from obelix.modbus_client import get_clients, modbus_lock
from obelix.r302_manager import R302Controller
from obelix.utils import log

sbr_controller = None

class SBRController:
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.clients = get_clients()
        self.r302_unit = 0
        self.r302_ctrl = R302Controller(unit_index=self.r302_unit)
        self.start_event = threading.Event()
        self.timer = 0  # Timer in seconden
        if get_setting('sbr_cycle_active', '0') == '0':
            self.set_auto_relays_off()
            self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')

    def set_auto_relays_off(self):
        inst = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            mode = self.r302_ctrl.get_mode(coil)
            if mode == 'AUTO' and get_relay_state(self.r302_unit, coil) != 'OFF':
                with modbus_lock:
                    inst.write_bit(coil, False, functioncode=5)
                    save_relay_state(self.r302_unit, coil, 'OFF')
                    self.socketio.emit('relay_toggled',
                                      {'unit_idx': self.r302_unit, 'coil_idx': coil, 'state': 'OFF'},
                                      namespace='/relays')
                    self.socketio.emit('r302_update',
                                      self.r302_ctrl.get_status(),
                                      namespace='/r302')
                log(f"🔧 Set AUTO relay {coil} ({Config.R302_RELAY_MAPPING[coil]}) to OFF")

    def stop(self):
        self.start_event.clear()
        set_setting('sbr_cycle_active', '0')
        self.set_auto_relays_off()
        log("▶ SBRController: STOP gedrukt")
        self.socketio.emit('sbr_status', {'active': False}, namespace='/sbr')
        self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')

    def reset(self):
        self.timer = 0
        log("▶ SBRController: RESET gedrukt")
        self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')

    def start(self):
        self.start_event.set()
        set_setting('sbr_cycle_active', '1')
        log("▶ SBRController: START gedrukt")
        self.socketio.emit('sbr_status', {'active': True}, namespace='/sbr')

    def run(self):
        global sbr_controller
        sbr_controller = self
        log("▶ SBRController: Thread gestart")
        while True:
            self.start_event.wait()
            log("🚀 Cycle gestart")
            while self.timer < 100 and self.start_event.is_set():
                self.socketio.sleep(1)
                self.timer += 1
                self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')
            if self.timer >= 100:
                self.timer = 0  # Reset voor herhaling
                self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')
            if not self.start_event.is_set():
                log("🔄 Cycle gestopt")
                continue
            log("✅ Cycle klaar")

def start_sbr_controller(socketio: SocketIO):
    global sbr_controller
    sbr_controller = SBRController(socketio)
    th = threading.Thread(target=sbr_controller.run, daemon=True)
    th.start()