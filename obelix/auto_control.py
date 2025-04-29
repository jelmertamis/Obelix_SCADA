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
        self.socketio    = socketio
        self.clients     = get_clients()
        self.r302_unit   = 0
        self.r302_ctrl   = R302Controller(unit_index=self.r302_unit)
        self.start_event = threading.Event()
        self.timer       = 0

        # Lees fasetijden (minuten) uit DB, met fallback
        infl = float(get_setting('sbr_influent_time_minutes', None)
                     or get_setting('sbr_cycle_time_minutes', '1.66667'))
        effl = float(get_setting('sbr_effluent_time_minutes', None)
                     or get_setting('sbr_cycle_time_minutes', '1.66667'))
        self.influent_time = infl
        self.effluent_time = effl
        self._update_phase_secs()

        # Bij inactiviteit: zet AUTO-relays uit en stuur status + tijden
        if get_setting('sbr_cycle_active', '0') == '0':
            self._set_all_auto_off()
            self._emit_status()
            self._emit_phase_times()

    def _update_phase_secs(self):
        """Converteer minuten naar seconden."""
        self.influent_secs = int(self.influent_time * 60)
        self.effluent_secs = int(self.effluent_time * 60)

    def _set_all_auto_off(self):
        inst = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            if self.r302_ctrl.get_mode(coil) == 'AUTO' and get_relay_state(self.r302_unit, coil) != 'OFF':
                with modbus_lock:
                    inst.write_bit(coil, False, functioncode=5)
                    save_relay_state(self.r302_unit, coil, 'OFF')
                log(f"⚙ Set AUTO relay {coil} off during idle")
        self.socketio.emit('r302_update', self.r302_ctrl.get_status(), namespace='/r302')

    def _apply_phase(self, phase_coil):
        inst = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            if self.r302_ctrl.get_mode(coil) == 'AUTO':
                want_on = (coil == phase_coil)
                want = 'ON' if want_on else 'OFF'
                if get_relay_state(self.r302_unit, coil) != want:
                    with modbus_lock:
                        inst.write_bit(coil, want_on, functioncode=5)
                        save_relay_state(self.r302_unit, coil, want)
                    label = 'Influent' if coil == 0 else 'Effluent'
                    log(f"⚙ Phase {label}: set relay {coil} to {want}")
        self.socketio.emit('r302_update', self.r302_ctrl.get_status(), namespace='/r302')

    def set_phase_times(self, influent_min: float, effluent_min: float):
        set_setting('sbr_influent_time_minutes', str(influent_min))
        set_setting('sbr_effluent_time_minutes', str(effluent_min))
        self.influent_time = influent_min
        self.effluent_time = effluent_min
        self._update_phase_secs()
        log(f"⏱ SBRController: Influent={influent_min}m ({self.influent_secs}s), "
            f"Effluent={effluent_min}m ({self.effluent_secs}s)")
        self._emit_phase_times()

    def _emit_phase_times(self):
        self.socketio.emit('sbr_phase_times', {
            'influent_minutes': self.influent_time,
            'influent_seconds': self.influent_secs,
            'effluent_minutes': self.effluent_time,
            'effluent_seconds': self.effluent_secs
        }, namespace='/sbr')

    def stop(self):
        self.start_event.clear()
        set_setting('sbr_cycle_active', '0')
        self._set_all_auto_off()
        log("⏹ SBRController: STOP gedrukt, alles AUTO-OFF")
        self._emit_status()

    def reset(self):
        self.timer = 0
        log("🔄 SBRController: RESET gedrukt")
        self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')

    def start(self):
        self.start_event.set()
        set_setting('sbr_cycle_active', '1')
        log("▶ SBRController: START gedrukt")
        self.socketio.emit('sbr_status', {'active': True}, namespace='/sbr')

    def _emit_status(self):
        active = self.start_event.is_set()
        self.socketio.emit('sbr_status', {'active': active}, namespace='/sbr')
        self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')

    def run(self):
        global sbr_controller
        sbr_controller = self
        log("▶ SBRController: Thread gestart")
        while True:
            self.start_event.wait()
            log("🚀 SBR cycle gestart")

            if not self.start_event.is_set():
                continue
            self._phase_loop(phase_coil=0)

            if not self.start_event.is_set():
                continue
            self._phase_loop(phase_coil=1)

            self.timer = 0
            log("✅ Volledige SBR cycle klaar")

    def _phase_loop(self, phase_coil):
        phase_name = 'influent' if phase_coil == 0 else 'effluent'
        self._apply_phase(phase_coil)

        elapsed = 0
        while self.start_event.is_set():
            duration = getattr(self, f"{phase_name}_secs")
            if elapsed >= duration:
                break
            self.socketio.sleep(1)
            self.timer += 1
            elapsed += 1
            self.socketio.emit('sbr_timer', {
                'timer': self.timer,
                'phase': phase_name,
                'phase_elapsed': elapsed,
                'phase_duration': duration
            }, namespace='/sbr')

def start_sbr_controller(socketio: SocketIO):
    global sbr_controller
    sbr_controller = SBRController(socketio)
    th = threading.Thread(target=sbr_controller.run, daemon=True)
    th.start()
