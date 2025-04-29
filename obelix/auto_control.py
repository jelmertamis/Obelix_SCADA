# obelix/auto_control.py

import threading
import itertools
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
        # oneindige cyclus: influent -> react -> effluent
        self._phase_cycle  = itertools.cycle(['influent', 'react', 'effluent'])
        self.current_phase = None
        self.phase_elapsed = 0

        # laad fasetijden (minuten) uit DB, met fallback
        base = get_setting('sbr_cycle_time_minutes', '1.66667')
        self.influent_time = float(get_setting('sbr_influent_time_minutes') or base)
        self.react_time    = float(get_setting('sbr_react_time_minutes')    or base)
        self.effluent_time = float(get_setting('sbr_effluent_time_minutes') or base)
        self._update_phase_secs()

        # init UI: inactive en alle AUTO-relays uit
        self._emit_status()
        self._auto_off_all()

    def _update_phase_secs(self):
        self.influent_secs = int(self.influent_time * 60)
        self.react_secs    = int(self.react_time    * 60)
        self.effluent_secs = int(self.effluent_time * 60)

    def set_phase_times(self, infl_min, react_min, effl_min):
        set_setting('sbr_influent_time_minutes',  str(infl_min))
        set_setting('sbr_react_time_minutes',     str(react_min))
        set_setting('sbr_effluent_time_minutes',  str(effl_min))
        self.influent_time = infl_min
        self.react_time    = react_min
        self.effluent_time = effl_min
        self._update_phase_secs()
        log(f"⏱ Phasetijden ingesteld: Influent={self.influent_secs}s, React={self.react_secs}s, Effluent={self.effluent_secs}s")
        self._emit_phase_times()

    def start(self):
        if not self.start_event.is_set():
            # als nog geen fase gekozen is, start bij influent
            if self.current_phase is None:
                self.current_phase = next(self._phase_cycle)
                self.phase_elapsed = 0
                self.timer = 0
            self.start_event.set()
            log("▶ START pressed")
            self._emit_status()

    def stop(self):
        if self.start_event.is_set():
            self.start_event.clear()
            log("⏹ STOP pressed (pauze)")
            self._emit_status()
            self._auto_off_all()

    def reset(self):
        # Zet alles terug naar fase 1 (influent), 0s, zonder automatisch te starten
        # self.start_event.clear()
        self.timer = 0
        self.current_phase = 'influent'
        self.phase_elapsed = 0
        log("🔄 RESET pressed — terug naar fase INFLUENT, 0s")
        # Direct de influent-relay aan (en rest uit)
        self._apply_phase('influent')
        # Update UI
        self._emit_status()
        self.socketio.emit('sbr_timer', {'timer': 0, 'phase': 'influent', 'phase_elapsed': 0, 'phase_duration': self.influent_secs}, namespace='/sbr')

    def _emit_status(self):
        self.socketio.emit('sbr_status', {'active': self.start_event.is_set()}, namespace='/sbr')
        self.socketio.emit('sbr_timer',  {'timer': self.timer},                      namespace='/sbr')

    def _emit_phase_times(self):
        data = {
            'influent_minutes': self.influent_time,
            'influent_seconds': self.influent_secs,
            'react_minutes':    self.react_time,
            'react_seconds':    self.react_secs,
            'effluent_minutes': self.effluent_time,
            'effluent_seconds': self.effluent_secs
        }
        self.socketio.emit('sbr_phase_times', data, namespace='/sbr')

    def _auto_off_all(self):
        inst = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            if mode == 'AUTO' and get_relay_state(self.r302_unit, coil) != 'OFF':
                with modbus_lock:
                    inst.write_bit(coil, False, functioncode=5)
                    save_relay_state(self.r302_unit, coil, 'OFF')
                log(f"⚙ AUTO relay {coil} off")
                self.socketio.emit('relay_toggled', {'unit_idx': self.r302_unit, 'coil_idx': coil, 'state': 'OFF'}, namespace='/relays')
        from obelix.r302_manager import R302Controller
        self.socketio.emit('r302_update', R302Controller(self.r302_unit).get_status(), namespace='/r302')

    def _apply_phase(self, phase):
        coil_map = {'influent': 0, 'effluent': 1}
        target = coil_map.get(phase)
        inst = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            if mode != 'AUTO':
                continue
            want_on = (coil == target)
            with modbus_lock:
                inst.write_bit(coil, want_on, functioncode=5)
                save_relay_state(self.r302_unit, coil, 'ON' if want_on else 'OFF')
            log(f"⚙ Phase {phase}: AUTO relay {coil} → {'ON' if want_on else 'OFF'}")
            self.socketio.emit('relay_toggled', {'unit_idx': self.r302_unit, 'coil_idx': coil, 'state': 'ON' if want_on else 'OFF'}, namespace='/relays')
        from obelix.r302_manager import R302Controller
        self.socketio.emit('r302_update', R302Controller(self.r302_unit).get_status(), namespace='/r302')

    def run(self):
        global sbr_controller
        sbr_controller = self
        log("▶ SBR thread started")
        while True:
            self.socketio.sleep(1)
            if not self.start_event.is_set():
                continue

            # Nieuwe fase initialisatie
            if self.phase_elapsed == 0:
                if self.current_phase == 'react':
                    self._auto_off_all()
                else:
                    self._apply_phase(self.current_phase)

            # Tel door
            self.phase_elapsed += 1
            self.timer += 1
            secs = getattr(self, f"{self.current_phase}_secs")
            self.socketio.emit('sbr_timer', {
                'timer':          self.timer,
                'phase':          self.current_phase,
                'phase_elapsed':  self.phase_elapsed,
                'phase_duration': secs
            }, namespace='/sbr')

            # Einde fase → volgende fase, maar reset cycle-timer alleen bij INF->REACT overgang
            if self.phase_elapsed >= secs:
                prev = self.current_phase
                self.current_phase = next(self._phase_cycle)
                self.phase_elapsed = 0
                if prev == 'effluent':
                    # pas wanneer we van effluent terug naar influent komen
                    self.timer = 0

def start_sbr_controller(socketio: SocketIO):
    global sbr_controller
    sbr_controller = SBRController(socketio)
    threading.Thread(target=sbr_controller.run, daemon=True).start()
