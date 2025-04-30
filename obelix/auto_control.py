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
        # Fase-cyclus: influent -> react -> effluent -> wait
        self._phase_cycle  = itertools.cycle(['influent', 'react', 'effluent', 'wait'])
        self.current_phase = None
        self.phase_elapsed = 0

        # Laad fasetijden (in minuten) uit DB, met fallback
        base = get_setting('sbr_cycle_time_minutes', '1.66667')
        self.influent_time = float(get_setting('sbr_influent_time_minutes') or base)
        self.react_time    = float(get_setting('sbr_react_time_minutes')    or base)
        self.effluent_time = float(get_setting('sbr_effluent_time_minutes') or base)
        self.wait_time     = float(get_setting('sbr_wait_time_minutes')     or '0.5')
        self._update_phase_secs()

        # Init UI: status en alle AUTO-relays uit
        self._emit_status()
        self._auto_off_all()

    def _update_phase_secs(self):
        self.influent_secs = int(self.influent_time * 60)
        self.react_secs    = int(self.react_time    * 60)
        self.effluent_secs = int(self.effluent_time * 60)
        self.wait_secs     = int(self.wait_time     * 60)

    def set_phase_times(self, infl_min, react_min, effl_min, wait_min=None):
        # Bewaar de eerste drie tijden
        set_setting('sbr_influent_time_minutes',  str(infl_min))
        set_setting('sbr_react_time_minutes',     str(react_min))
        set_setting('sbr_effluent_time_minutes',  str(effl_min))
        # Bewaar de wait-tijd als die meegegeven is
        if wait_min is not None:
            set_setting('sbr_wait_time_minutes', str(wait_min))
            self.wait_time = wait_min

        # Update intern
        self.influent_time = infl_min
        self.react_time    = react_min
        self.effluent_time = effl_min
        self._update_phase_secs()
        log(
            f"⏱ Phasetijden ingesteld: Influent={self.influent_secs}s, "
            f"React={self.react_secs}s, Effluent={self.effluent_secs}s, "
            f"Wait={self.wait_secs}s"
        )
        self._emit_phase_times()

    def start(self):
        if not self.start_event.is_set():
            # Eerste keer starten: initialiseert fase en teller
            if self.current_phase is None:
                self.current_phase = next(self._phase_cycle)
                self.phase_elapsed = 0
                self.timer = 0

            # Activeer de cycle
            self.start_event.set()
            log("▶ START pressed")
            self._emit_status()

            # Direct de juiste relaisstand toepassen voor de huidige fase
            if self.current_phase == 'wait':
                # In de wait-fase zet je alle AUTO-relais uit
                self._auto_off_all()
            else:
                # In andere fases pas je de fase-logica toe
                self._apply_phase(self.current_phase)


    def stop(self):
        if self.start_event.is_set():
            self.start_event.clear()
            log("⏸ STOP pressed (pauze)")
            self._emit_status()
            self._auto_off_all()

    def reset(self):
        # Reset naar fase 'influent', timer 0, behoud actieve status
        self.timer = 0
        self.current_phase = 'influent'
        self.phase_elapsed = 0
        log("🔄 RESET pressed — terug naar fase INFLUENT, 0s")

        if self.start_event.is_set():
            # Als de cycle draait, pas de normale fase-logica toe
            self._apply_phase('influent')
        else:
            # Als gepauzeerd, zet alle AUTO-relais uit
            self._auto_off_all()

        # Status en timer naar de client sturen
        self._emit_status()
        self.socketio.emit('sbr_timer', {
            'timer':          0,
            'phase':          'influent',
            'phase_elapsed':  0,
            'phase_duration': self.influent_secs
        }, namespace='/sbr')

    
    def _emit_status(self):
        self.socketio.emit('sbr_status', {'active': self.start_event.is_set()}, namespace='/sbr')
        self.socketio.emit('sbr_timer',  {'timer': self.timer},                          namespace='/sbr')

    def _emit_phase_times(self):
        data = {
            'influent_minutes': self.influent_time,
            'influent_seconds': self.influent_secs,
            'react_minutes':    self.react_time,
            'react_seconds':    self.react_secs,
            'effluent_minutes': self.effluent_time,
            'effluent_seconds': self.effluent_secs,
            'wait_minutes':     self.wait_time,
            'wait_seconds':     self.wait_secs
        }
        self.socketio.emit('sbr_phase_times', data, namespace='/sbr')

    def _auto_off_all(self):
        inst = self.clients[self.r302_unit]
        # Voor iedere R302-relay: indien in AUTO en nog niet OFF, zet uit
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            current_state = get_relay_state(self.r302_unit, coil)
            if mode == 'AUTO' and current_state != 'OFF':
                with modbus_lock:
                    inst.write_bit(coil, False, functioncode=5)
                    save_relay_state(self.r302_unit, coil, 'OFF')

                # Stuur update naar alle /relays-clients
                self.socketio.emit('relay_toggled', {
                    'unit_idx': self.r302_unit,
                    'coil_idx': coil,
                    'state':    'OFF'
                }, namespace='/relays')

        # Na auto-off: stuur nieuwe status van alle R302-coils naar alle /r302-clients
        from obelix.r302_manager import R302Controller
        status = R302Controller(self.r302_unit).get_status()
        self.socketio.emit('r302_update', status, namespace='/r302')


    def _apply_phase(self, phase):
        # Bij 'wait' enkel alle relais uit
        if phase == 'wait':
            self._auto_off_all()
            return

        coil_map = {'influent': 0, 'effluent': 1}
        target   = coil_map.get(phase)
        inst     = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            if mode != 'AUTO':
                continue
            want_on = (coil == target)
            with modbus_lock:
                inst.write_bit(coil, want_on, functioncode=5)
                save_relay_state(self.r302_unit, coil, 'ON' if want_on else 'OFF')
            log(f"✖ Phase {phase}: AUTO relay {coil} → {'ON' if want_on else 'OFF'}")
            self.socketio.emit('relay_toggled', {
                'unit_idx': self.r302_unit,
                'coil_idx': coil,
                'state':    'ON' if want_on else 'OFF'
            }, namespace='/relays')
        from obelix.r302_manager import R302Controller
        self.socketio.emit('r302_update', R302Controller(self.r302_unit).get_status(), namespace='/r302')

    def run(self):
        global sbr_controller
        sbr_controller = self
        log("▶ SBR thread started")
        phases = ['influent', 'react', 'effluent', 'wait']

        while True:
            self.socketio.sleep(1)
            if not self.start_event.is_set():
                continue

            # Bepaal huidige fase
            phase = self.current_phase or phases[0]

            # Fase-init bij eerste seconde
            if self.phase_elapsed == 0:
                if phase == 'wait':
                    self._auto_off_all()
                else:
                    self._apply_phase(phase)

            # Tellers updaten
            self.phase_elapsed += 1
            self.timer += 1
            secs = getattr(self, f"{phase}_secs")
            self.socketio.emit('sbr_timer', {
                'timer':          self.timer,
                'phase':          phase,
                'phase_elapsed':  self.phase_elapsed,
                'phase_duration': secs
            }, namespace='/sbr')

            # Als fase klaar, ga naar volgende
            if self.phase_elapsed >= secs:
                idx = phases.index(phase)
                next_idx = (idx + 1) % len(phases)
                self.current_phase = phases[next_idx]
                self.phase_elapsed = 0
                if phase == 'effluent':
                    # reset globale timer na effluent
                    self.timer = 0

def start_sbr_controller(socketio: SocketIO):
    global sbr_controller
    sbr_controller = SBRController(socketio)
    threading.Thread(target=sbr_controller.run, daemon=True).start()
