# obelix/auto_control.py

import threading
from flask_socketio import SocketIO
from obelix.config import Config
from obelix.database import get_setting, set_setting, save_relay_state, get_relay_state
from obelix.modbus_client import get_clients, modbus_lock
from obelix.utils import log

sbr_controller = None

class SBRController:
    def __init__(self, socketio: SocketIO):
        self.socketio      = socketio
        self.clients       = get_clients()
        self.r302_unit     = 0
        self.start_event   = threading.Event()
        self.timer         = 0
        self.current_phase = None   # hou bij welke fase loopt

        # fasetijden uit DB
        base = get_setting('sbr_cycle_time_minutes', '1.66667')
        self.influent_time = float(get_setting('sbr_influent_time_minutes', None) or base)
        self.react_time    = float(get_setting('sbr_react_time_minutes',    None) or base)
        self.effluent_time = float(get_setting('sbr_effluent_time_minutes', None) or base)
        self._update_phase_secs()

        # bij inactief: alle AUTO-relays uit en status/tijden emitten
        if get_setting('sbr_cycle_active', '0') == '0':
            self._auto_off_all()
            self._emit_status()
            self._emit_phase_times()

    def _update_phase_secs(self):
        self.influent_secs = int(self.influent_time * 60)
        self.react_secs    = int(self.react_time    * 60)
        self.effluent_secs = int(self.effluent_time * 60)

    def _auto_off_all(self):
        inst = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            if mode == 'AUTO' and get_relay_state(self.r302_unit, coil) != 'OFF':
                with modbus_lock:
                    inst.write_bit(coil, False, functioncode=5)
                    save_relay_state(self.r302_unit, coil, 'OFF')
                log(f"⚙ AUTO relay {coil} off")
        # update UI
        from obelix.r302_manager import R302Controller
        status = R302Controller(self.r302_unit).get_status()
        self.socketio.emit('r302_update', status, namespace='/r302')

    def _apply_phase(self, phase: str):
        coil_map = {'influent': 0, 'effluent': 1}
        inst = self.clients[self.r302_unit]
        target = coil_map[phase]
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            if mode != 'AUTO':
                continue
            want_on = (coil == target)
            want    = 'ON' if want_on else 'OFF'
            if get_relay_state(self.r302_unit, coil) != want:
                with modbus_lock:
                    inst.write_bit(coil, want_on, functioncode=5)
                    save_relay_state(self.r302_unit, coil, want)
                log(f"⚙ Phase {phase}: AUTO relay {coil} → {want}")
        from obelix.r302_manager import R302Controller
        status = R302Controller(self.r302_unit).get_status()
        self.socketio.emit('r302_update', status, namespace='/r302')

    def set_phase_times(self, influent_min: float, react_min: float, effluent_min: float):
        set_setting('sbr_influent_time_minutes',  str(influent_min))
        set_setting('sbr_react_time_minutes',     str(react_min))
        set_setting('sbr_effluent_time_minutes',  str(effluent_min))
        self.influent_time = influent_min
        self.react_time    = react_min
        self.effluent_time = effluent_min
        self._update_phase_secs()
        log(f"⏱ Updated phases: Influent={self.influent_secs}s, React={self.react_secs}s, Effluent={self.effluent_secs}s")
        self._emit_phase_times()

    def _emit_phase_times(self):
        self.socketio.emit('sbr_phase_times', {
            'influent_minutes': self.influent_time,
            'influent_seconds': self.influent_secs,
            'react_minutes':    self.react_time,
            'react_seconds':    self.react_secs,
            'effluent_minutes': self.effluent_time,
            'effluent_seconds': self.effluent_secs
        }, namespace='/sbr')

    def stop(self):
        self.start_event.clear()
        set_setting('sbr_cycle_active', '0')
        self._auto_off_all()
        log("⏹ STOP pressed")
        self._emit_status()

    def reset(self):
        self.timer = 0
        log("🔄 RESET pressed")
        self.socketio.emit('sbr_timer', {'timer': self.timer}, namespace='/sbr')

    def start(self):
        self.start_event.set()
        set_setting('sbr_cycle_active', '1')
        log("▶ START pressed")
        self.socketio.emit('sbr_status', {'active': True}, namespace='/sbr')

    def _emit_status(self):
        active = self.start_event.is_set()
        self.socketio.emit('sbr_status', {'active': active}, namespace='/sbr')
        self.socketio.emit('sbr_timer',  {'timer': self.timer},   namespace='/sbr')

    def run(self):
        global sbr_controller
        sbr_controller = self
        log("▶ SBR thread started")
        while True:
            self.start_event.wait()
            log("🚀 Cycle started")

            # fase 1
            if not self.start_event.is_set(): continue
            self.current_phase = 'influent'
            self._phase_loop('influent')

            # fase 2
            if not self.start_event.is_set(): continue
            self.current_phase = 'react'
            self._phase_loop('react')

            # fase 3
            if not self.start_event.is_set(): continue
            self.current_phase = 'effluent'
            self._phase_loop('effluent')

            self.timer = 0
            log("✅ Cycle finished")

    def _phase_loop(self, phase: str):
        if phase == 'react':
            self._auto_off_all()
        else:
            self._apply_phase(phase)

        elapsed = 0
        while self.start_event.is_set():
            duration = getattr(self, f"{phase}_secs")
            if elapsed >= duration:
                break
            self.socketio.sleep(1)
            self.timer += 1
            elapsed += 1
            self.socketio.emit('sbr_timer', {
                'timer':          self.timer,
                'phase':          phase,
                'phase_elapsed':  elapsed,
                'phase_duration': duration
            }, namespace='/sbr')

def start_sbr_controller(socketio: SocketIO):
    global sbr_controller
    sbr_controller = SBRController(socketio)
    th = threading.Thread(target=sbr_controller.run, daemon=True)
    th.start()
