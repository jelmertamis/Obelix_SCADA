# obelix/auto_control.py

import threading
import itertools
from flask_socketio import SocketIO
from obelix.config import Config
from obelix.database import (
    get_setting, set_setting,
    save_relay_state, get_relay_state,
    get_calibration, get_dummy_value
)
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

        # Fase-cyclus
        self.phases = ['influent', 'react', 'effluent', 'wait', 'dose_nutrients','wait_after_N']
        self._phase_cycle  = itertools.cycle(self.phases)
        self.current_phase = None
        self.phase_elapsed = 0

        # Laad fasetijden
        DEFAULT_PHASE_MIN = '7'
        self.react_time    = float(get_setting('sbr_react_time_minutes',    DEFAULT_PHASE_MIN))
        self.wait_time     = float(get_setting('sbr_wait_time_minutes',     DEFAULT_PHASE_MIN))
        self.dose_time     = float(get_setting('sbr_dose_nutrients_time_minutes', DEFAULT_PHASE_MIN))
        self.wait_after_N_time = float(get_setting('sbr_wait_after_N_time_minutes', DEFAULT_PHASE_MIN))

        DEFAULT_CYCLE_MAX = '720'
        self.cycle_time_max = float(get_setting('sbr_cycle_time_max_minutes', DEFAULT_CYCLE_MAX))

        # Level-drempel
        self.influent_threshold = float(get_setting('sbr_influent_level_threshold', '0'))
        self.effluent_threshold = float(get_setting('sbr_effluent_level_threshold', '0'))

        # Sensor-unit/kanaal (slave ID 5, kanaal 0)
        self.level_unit    = next(
            i for i, u in enumerate(Config.UNITS)
            if u['type']=='analog' and u['slave_id']==5
        )
        self.level_channel = 0

        self._update_phase_end_conditions()

        # Init UI
        self._emit_status()
        self._auto_off_all()

    def _update_phase_end_conditions(self):
        self.phase_end = {
            'react':            int(self.react_time * 60),
            'wait':             int(self.wait_time * 60),
            'dose_nutrients':   int(self.dose_time * 60),
            'wait_after_N':     int(self.wait_after_N_time * 60),
        }

    def _get_phase_target(self, phase):
        """
        Bepaalt het doelcriterium voor elke fase:
        – Voor influent en effluent (bij drempel >= 0) op level
        – Anders op tijd (in seconden)
        """
        if phase == 'influent' and self.influent_threshold >= 0:
            return self.influent_threshold
        if phase == 'effluent' and self.effluent_threshold >= 0:
            return self.effluent_threshold
        return self.phase_end.get(phase, 0)


    def set_phase_times(self, react, wait, dose_nutrients, wait_after_N):
        # 1) Persist in de DB met de juiste keys
        set_setting('sbr_react_time_minutes',          str(react))
        set_setting('sbr_wait_time_minutes',          str(wait))
        set_setting('sbr_dose_nutrients_time_minutes', str(dose_nutrients))
        set_setting('sbr_wait_after_N_time_minutes', str(wait_after_N))

        # 2) Update je instance-variabelen
        self.react_time   = react
        self.wait_time    = wait
        self.dose_time    = dose_nutrients
        self.wait_after_N_time = wait_after_N


        # 3) Herbereken de phase_end dict
        self._update_phase_end_conditions()

        # 4) Log en push naar de UI
        log(f"SBR times updated: react={react}m, wait={wait}m, dose={dose_nutrients}m")
        self._emit_phase_times()


    def start(self):
        if not self.start_event.is_set():
            if self.current_phase is None:
                self.current_phase = next(self._phase_cycle)
                self.phase_elapsed = 0
                self.timer = 0
            self.start_event.set()
            log("▶ SBR START")
            self._emit_status()
            self._apply_phase(self.current_phase)

    def stop(self):
        if self.start_event.is_set():
            self.start_event.clear()
            log("⏸ SBR STOP")
            self._emit_status()
            self._auto_off_all()

    def reset(self):
        self.timer = 0
        self.current_phase = 'influent'
        self.phase_elapsed = 0
        log("🔄 SBR RESET to influent")
        if self.start_event.is_set():
            self._apply_phase('influent')
        else:
            self._auto_off_all()
        self._emit_status()
        self.socketio.emit('sbr_timer', {
            'timer':         0,
            'phase':         'influent',
            'phase_elapsed': 0,
            'phase_target':  self._get_phase_target('influent'),
            'actual_level':  None
        }, namespace='/sbr')

    def _emit_status(self):
        self.socketio.emit('sbr_status', {'active': self.start_event.is_set()}, namespace='/sbr')
        self.socketio.emit('sbr_timer',  {'timer': self.timer}, namespace='/sbr')

    def _emit_phase_times(self):
        self.socketio.emit('sbr_phase_times', {
            'react_minutes':           self.react_time,
            'react_seconds':           self._get_phase_target('react'),
            'wait_minutes':            self.wait_time,
            'wait_seconds':            self._get_phase_target('wait'),
            'dose_nutrients_minutes':  self.dose_time,
            'dose_nutrients_seconds':  self._get_phase_target('dose_nutrients'),
            'wait_after_N_minutes':    self.wait_after_N_time,
            'wait_after_N_seconds':    self._get_phase_target('wait_after_N'),
            'cycle_time_max_minutes':  self.cycle_time_max            
        }, namespace='/sbr')


    def _auto_off_all(self):
        inst = self.clients[self.r302_unit]
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            state= get_relay_state(self.r302_unit, coil)
            if mode == 'AUTO' and state != 'OFF':
                with modbus_lock:
                    inst.write_bit(coil, False, functioncode=5)
                    save_relay_state(self.r302_unit, coil, 'OFF')
                self.socketio.emit('relay_toggled', {
                    'unit_idx': self.r302_unit,
                    'coil_idx': coil,
                    'state':    'OFF'
                }, namespace='/relays')
        from obelix.r302_manager import R302Controller
        self.socketio.emit('r302_update',
                           R302Controller(self.r302_unit).get_status(),
                           namespace='/r302')

    def _apply_phase(self, phase):
        if phase == 'wait':
            return self._auto_off_all()
        inst = self.clients[self.r302_unit]
        coil_map = {
            'influent': 0,
            'effluent': 1,
            'dose_nutrients': 2
            }
        target   = coil_map.get(phase)
        for coil in Config.R302_RELAY_MAPPING:
            mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            if mode != 'AUTO':
                continue
            want = (coil == target)
            with modbus_lock:
                inst.write_bit(coil, want, functioncode=5)
                save_relay_state(self.r302_unit, coil, 'ON' if want else 'OFF')
            self.socketio.emit('relay_toggled', {
                'unit_idx': self.r302_unit,
                'coil_idx': coil,
                'state':    'ON' if want else 'OFF'
            }, namespace='/relays')
        from obelix.r302_manager import R302Controller
        self.socketio.emit('r302_update',
                           R302Controller(self.r302_unit).get_status(),
                           namespace='/r302')

    def run(self):
        global sbr_controller
        sbr_controller = self
        log("🔄 SBR thread started")
        phases = self.phases

        while True:
            if not self.start_event.is_set():
                self.socketio.sleep(1)
                continue
            
            # Controleer op maximale cyclus duur
            if self.timer >= self.cycle_time_max * 60:
                log("Cycle time exceeded max, restarting cycle at influent")
                self.reset()
                continue

            phase = self.current_phase or 'influent'

            # Lees dummy override of echt register
            raw = None
            dummy = get_dummy_value(self.level_unit, self.level_channel)
            if dummy is not None:
                raw = dummy
            else:
                try:
                    with modbus_lock:
                        raw = self.clients[self.level_unit].read_register(
                            self.level_channel, functioncode=4
                        )
                except:
                    raw = None

            # Bereken calibrated actual
            actual = None
            if raw is not None:
                cal = get_calibration(self.level_unit, self.level_channel)
                actual = raw * cal['scale'] + cal['offset']

            # Overgang voor influent op basis level
            if phase == 'influent' and self.influent_threshold >= 0 and actual is not None:
                if actual >= self.influent_threshold:
                    idx = phases.index(phase)
                    next_p = phases[(idx + 1) % len(phases)]
                    self.phase_elapsed = 0
                    log(f"🔄 Overgang naar volgende fase: {next_p}")
                    log((idx + 1) % len(phases))
                    if (idx + 1) % len(phases) == 0:
                        log("setting self.timer = 0")
                        self.timer = 0
                    self.current_phase = next_p
                    self._apply_phase(next_p)
                    self.socketio.emit('sbr_timer', {
                        'timer':         self.timer,
                        'phase':         next_p,
                        'phase_elapsed': 0,
                        'phase_target':  self._get_phase_target(next_p),
                        'actual_level':  None
                    }, namespace='/sbr')
                    continue
            elif phase == 'effluent' and self.effluent_threshold >= 0 and actual is not None:
                if actual <= self.effluent_threshold:
                    idx = phases.index(phase)
                    next_p = phases[(idx + 1) % len(phases)]
                    self.phase_elapsed = 0
                    log(f"🔄 Overgang naar volgende fase: {next_p}")
                    log((idx + 1) % len(phases))
                    if (idx + 1) % len(phases) == 0:
                        log("setting self.timer = 0")
                        self.timer = 0
                    self.current_phase = next_p
                    self._apply_phase(next_p)
                    self.socketio.emit('sbr_timer', {
                        'timer':         self.timer,
                        'phase':         next_p,
                        'phase_elapsed': 0,
                        'phase_target':  self._get_phase_target(next_p),
                        'actual_level':  None
                    }, namespace='/sbr')
                    continue
            else:
                if self.phase_elapsed >= self.phase_end.get(phase, 0):
                    
                    idx = phases.index(phase)
                    next_p = phases[(idx + 1) % len(phases)]
                    self.phase_elapsed = 0
                    log(f"🔄 Overgang naar volgende fase: {next_p}")
                    log((idx + 1) % len(phases))
                    if (idx + 1) % len(phases) == 0:
                        log("setting self.timer = 0")
                        self.timer = 0
                    self.current_phase = next_p
                    self._apply_phase(next_p)
                    self.socketio.emit('sbr_timer', {
                        'timer':         self.timer,
                        'phase':         next_p,
                        'phase_elapsed': 0,
                        'phase_target':  self._get_phase_target(next_p),
                        'actual_level':  None
                    }, namespace='/sbr')
                    continue

            if self.phase_elapsed == 0:
                self._apply_phase(phase)

            # Emit status met actual_level
            self.socketio.emit('sbr_timer', {
                'timer':          self.timer,
                'phase':          phase,
                'phase_elapsed':  self.phase_elapsed,
                'phase_target':   self._get_phase_target(phase),
                'actual_level':   actual
            }, namespace='/sbr')

            self.socketio.sleep(1)
            self.phase_elapsed += 1
            self.timer += 1

def start_sbr_controller(socketio: SocketIO):
    global sbr_controller
    sbr_controller = SBRController(socketio)
    threading.Thread(target=sbr_controller.run, daemon=True).start()
