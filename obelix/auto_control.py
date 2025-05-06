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
        DEFAULT_PHASE_MIN = 7
        self.react_time    = float(get_setting('sbr_react_time_minutes',    DEFAULT_PHASE_MIN))
        self.wait_time     = float(get_setting('sbr_wait_time_minutes',     DEFAULT_PHASE_MIN))
        self.dose_time     = float(get_setting('sbr_dose_nutrients_time_minutes', DEFAULT_PHASE_MIN))
        self.wait_after_N_time = float(get_setting('sbr_wait_after_N_time_minutes', DEFAULT_PHASE_MIN))

        DEFAULT_CYCLE_MAX = 720
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

        # Temperatuursensor op slave ID 5, kanaal 2
        self.temp_channel  = 2

        # Laad heating valve setpoints (°C)
        DEFAULT_HEAT_ON  = 30
        DEFAULT_HEAT_OFF = 25
        self.heat_on_temp  = float(get_setting('heating_valve_on_temp',  DEFAULT_HEAT_ON))
        self.heat_off_temp = float(get_setting('heating_valve_off_temp', DEFAULT_HEAT_OFF))


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
            self._apply_phase_logic_pumps(self.current_phase)

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
            self._apply_phase_logic_pumps('influent')
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

    def _apply_compressor_settings(self, phase: str):
        """
        Lees compressor instellingen uit DB en pas toe:
        - Digitale coils 3 (K303) en 4 (K304) ON/OFF
        - Analoge output channels 0 en 1 voor snelheidspercentage
        Schrijf alleen als de gewenste state/waarde verschilt van huidige.
        """
        inst_relay = self.clients[self.r302_unit]
        inst_aio   = self.clients[Config.AIO_IDX]
        for coil, ch in ((3, 0), (4, 1)):
            # lees instellingen
            mode_key = f'compressor_{phase}_k{303 if coil==3 else 304}_mode'
            pct_key  = f'compressor_{phase}_k{303 if coil==3 else 304}_pct'
            mode = get_setting(mode_key, 'OFF')
            pct  = float(get_setting(pct_key, '0'))
            # digitale relais: lees huidig
            current = (get_relay_state(self.r302_unit, coil) == 'ON')
            want = (mode == 'ON')
            log(f"Coil {coil}: current={current}, want={want}")
            if want != current:
                with modbus_lock:
                    inst_relay.write_bit(coil, want, functioncode=5)
                save_relay_state(self.r302_unit, coil, 'ON' if want else 'OFF')
                self.socketio.emit('relay_toggled', {
                    'unit_idx': self.r302_unit,
                    'coil_idx': coil,
                    'state':    'ON' if want else 'OFF'
                }, namespace='/relays')
            # analoge uitgang: vergelijk met DB
            prev_pct = get_setting(f'aio_setting_{ch}')
            log(f"AIO ch{ch}: prev_pct={prev_pct}, new_pct={pct}")
            if prev_pct is None or float(prev_pct) != pct:
                mA = 4.0 + (pct / 100.0) * 16.0
                raw = int((mA / 20.0) * 4095)
                with modbus_lock:
                    inst_aio.write_register(ch, raw, functioncode=6)
                set_setting(f'aio_setting_{ch}', pct)
                self.socketio.emit('aio_updated', {
                    'channel':     ch,
                    'raw_out':     raw,
                    'phys_out':    round(mA, 2),
                    'percent_out': pct
                }, namespace='/aio')
        log(f"Compressor settings applied for phase '{phase}'")
    
    def _check_heating_valve(self, temp_value):
        """Open/sluit coil 5 (heating valve) op basis van setpoints, alleen in AUTO."""
        from obelix.r302_manager import R302Controller
        coil = 5
        # Alleen handelen als de mode op AUTO staat
        mode = R302Controller(self.r302_unit).get_mode(coil)
        if mode != 'AUTO':
            return

        inst = self.clients[self.r302_unit]
        current_on = (get_relay_state(self.r302_unit, coil) == 'ON')

        if temp_value <= self.heat_on_temp and not current_on:
            with modbus_lock:
                inst.write_bit(coil, True, functioncode=5)
            save_relay_state(self.r302_unit, coil, 'ON')
            self.socketio.emit('relay_toggled', {
                'unit_idx': self.r302_unit,
                'coil_idx': coil,
                'state':    'ON'
            }, namespace='/relays')
            self.socketio.emit('r302_update',
                               R302Controller(self.r302_unit).get_status(),
                               namespace='/r302')

        elif temp_value >= self.heat_off_temp and current_on:
            with modbus_lock:
                inst.write_bit(coil, False, functioncode=5)
            save_relay_state(self.r302_unit, coil, 'OFF')
            self.socketio.emit('relay_toggled', {
                'unit_idx': self.r302_unit,
                'coil_idx': coil,
                'state':    'OFF'
            }, namespace='/relays')
            self.socketio.emit('r302_update',
                               R302Controller(self.r302_unit).get_status(),
                               namespace='/r302')

    def _monitor_temperature(self):
        """Lees en verwerk temperatuursensor, ongeacht cyclusstatus."""
        try:
            dummy = get_dummy_value(self.level_unit, self.temp_channel)
            
            if dummy is not None:
                raw = dummy
            else:
                with modbus_lock:
                    raw = self.clients[self.level_unit].read_register(
                        self.temp_channel, functioncode=4
                    )


            cal = get_calibration(self.level_unit, self.temp_channel)
            temp = raw * cal['scale'] + cal['offset']
            self._check_heating_valve(temp)
        except Exception as e:
            log(f"Error monitoring temperature: {e}")  
        
    def _apply_phase_logic_pumps(self, phase, influent_should_be_on=True):
        """
        Past pompstatus toe voor de gegeven fase. Voor influent fase wordt
        influent_should_be_on gebruikt om de pompstatus (ON/OFF) te bepalen.
        """
        log(f"🔍 Start _apply_phase_logic_pumps voor fase: {phase}, influent_should_be_on: {influent_should_be_on}")
        if phase == 'wait':
            log("🔍 Pauze-fase: alle pompen uit")
            return self._auto_off_all()

        try:
            inst = self.clients[self.r302_unit]
            log(f"🔍 Modbus-client verkregen voor unit {self.r302_unit}")

            phase_to_coils = {
                'influent': [0],
                'effluent': [1],
                'dose_nutrients': [2]
            }
            target_coils = phase_to_coils.get(phase, [])
            log(f"🔍 Target coils voor fase {phase}: {target_coils}")

            for coil in (0, 1, 2):
                mode = get_setting(f'r302_relay_{coil}_mode', 'AUTO')
                log(f"🔍 Coil {coil} modus: {mode}")
                if mode != 'AUTO':
                    log(f"🚰 Relais {coil} in {mode} modus, overslaan AUTO logica")
                    continue

                should_be_on = (coil in target_coils)
                # Pas should_be_on aan voor influent pomp
                if phase == 'influent' and coil == 0:
                    should_be_on = influent_should_be_on
                log(f"🔍 Coil {coil} should_be_on: {should_be_on}")

                try:
                    with modbus_lock:
                        log(f"🔍 Schrijven naar coil {coil}: {'ON' if should_be_on else 'OFF'}")
                        inst.write_bit(coil, should_be_on, functioncode=5)
                        save_relay_state(self.r302_unit, coil, 'ON' if should_be_on else 'OFF')
                    self.socketio.emit('relay_toggled', {
                        'unit_idx': self.r302_unit,
                        'coil_idx': coil,
                        'state': 'ON' if should_be_on else 'OFF'
                    }, namespace='/relays')
                except Exception as e:
                    log(f"❌ Fout bij schrijven naar coil {coil}: {e}")

            self._apply_compressor_settings(phase)
            from obelix.r302_manager import R302Controller
            self.socketio.emit('r302_update',
                               R302Controller(self.r302_unit).get_status(),
                               namespace='/r302')
        except Exception as e:
            log(f"❌ Fout in _apply_phase_logic_pumps: {e}")

    def run(self):
        global sbr_controller
        sbr_controller = self
        log("🔄 SBR thread started")
        phases = self.phases
        last_pulse_state = None

        while True:
            log(f"🔍 Run loop tick - start_event: {self.start_event.is_set()}, fase: {self.current_phase}, "
                f"phase_elapsed: {self.phase_elapsed}, timer: {self.timer}")
            self._monitor_temperature()

            if not self.start_event.is_set():
                log("🔍 Cyclus niet gestart, overslaan fase-logica")
                self.socketio.sleep(1)
                continue

            if self.timer >= self.cycle_time_max * 60:
                log("🔍 Cycle time exceeded max, restarting cycle at influent")
                self.reset()
                continue

            phase = self.current_phase or 'influent'
            log(f"🔍 Verwerken fase: {phase}")

            # Puls-pauze logica voor influent fase
            influent_should_be_on = True  # Standaard AAN voor niet-influent fases
            if phase == 'influent':
                pulse_time = float(get_setting('pulse_influent_seconds', '10.0'))
                pause_time = float(get_setting('pause_influent_seconds', '20.0'))
                cycle_time = pulse_time + pause_time
                log(f"🔍 Influent puls-pauze - Puls: {pulse_time}s, Pauze: {pause_time}s, Cycle: {cycle_time}s")

                if cycle_time > 0:
                    cycle_position = self.phase_elapsed % cycle_time
                    influent_should_be_on = (cycle_position < pulse_time)
                    current_state = 'ON' if influent_should_be_on else 'OFF'
                    log(f"🚰 Influent pomp: AUTO_{current_state} "
                        f"(puls {pulse_time}s, pauze {pause_time}s, positie {cycle_position:.1f}s)")

                    # Roep _apply_phase_logic_pumps aan bij staatverandering
                    if last_pulse_state != current_state:
                        log(f"🔍 Puls-pauze staat veranderd naar {current_state}, roep _apply_phase_logic_pumps aan")
                        self._apply_phase_logic_pumps('influent', influent_should_be_on=influent_should_be_on)
                        last_pulse_state = current_state
                else:
                    log("🔍 Ongeldige puls-pauze cyclus, pomp uit")
                    influent_should_be_on = False
                    if last_pulse_state != 'OFF':
                        self._apply_phase_logic_pumps('influent', influent_should_be_on=False)
                        last_pulse_state = 'OFF'

            raw = None
            dummy = get_dummy_value(self.level_unit, self.level_channel)
            if dummy is not None:
                log(f"🔍 Dummy niveau waarde: {dummy}")
                raw = dummy
            else:
                try:
                    with modbus_lock:
                        raw = self.clients[self.level_unit].read_register(
                            self.level_channel, functioncode=4
                        )
                        log(f"🔍 Modbus niveau waarde: {raw}")
                except Exception as e:
                    log(f"❌ Fout bij lezen niveau register: {e}")
                    raw = None

            actual = None
            if raw is not None:
                cal = get_calibration(self.level_unit, self.level_channel)
                actual = raw * cal['scale'] + cal['offset']
                log(f"🔍 Gekalibreerd niveau: {actual}")

            if phase == 'influent' and self.influent_threshold >= 0 and actual is not None:
                log(f"🔍 Influent fase - actual: {actual}, threshold: {self.influent_threshold}")
                if actual >= self.influent_threshold:
                    idx = phases.index(phase)
                    next_p = phases[(idx + 1) % len(phases)]
                    self.phase_elapsed = 0
                    log(f"🔄 Overgang naar volgende fase: {next_p}")
                    if (idx + 1) % len(phases) == 0:
                        log("🔍 Cyclus voltooid, timer reset")
                        self.timer = 0
                    self.current_phase = next_p
                    self._apply_phase_logic_pumps(next_p)
                    self.socketio.emit('sbr_timer', {
                        'timer': self.timer,
                        'phase': next_p,
                        'phase_elapsed': 0,
                        'phase_target': self._get_phase_target(next_p),
                        'actual_level': None
                    }, namespace='/sbr')
                    last_pulse_state = None
                    continue
            elif phase == 'effluent' and self.effluent_threshold >= 0 and actual is not None:
                log(f"🔍 Effluent fase - actual: {actual}, threshold: {self.effluent_threshold}")
                if actual <= self.effluent_threshold:
                    idx = phases.index(phase)
                    next_p = phases[(idx + 1) % len(phases)]
                    self.phase_elapsed = 0
                    log(f"🔄 Overgang naar volgende fase: {next_p}")
                    if (idx + 1) % len(phases) == 0:
                        log("🔍 Cyclus voltooid, timer reset")
                        self.timer = 0
                    self.current_phase = next_p
                    self._apply_phase_logic_pumps(next_p)
                    self.socketio.emit('sbr_timer', {
                        'timer': self.timer,
                        'phase': next_p,
                        'phase_elapsed': 0,
                        'phase_target': self._get_phase_target(next_p),
                        'actual_level': None
                    }, namespace='/sbr')
                    continue
            else:
                phase_end = self.phase_end.get(phase, 0)
                log(f"🔍 Tijdgebaseerde fase - phase_elapsed: {self.phase_elapsed}, phase_end: {phase_end}")
                if self.phase_elapsed >= phase_end:
                    idx = phases.index(phase)
                    next_p = phases[(idx + 1) % len(phases)]
                    self.phase_elapsed = 0
                    log(f"🔄 Overgang naar volgende fase: {next_p}")
                    if (idx + 1) % len(phases) == 0:
                        log("🔍 Cyclus voltooid, timer reset")
                        self.timer = 0
                    self.current_phase = next_p
                    self._apply_phase_logic_pumps(next_p)
                    self.socketio.emit('sbr_timer', {
                        'timer': self.timer,
                        'phase': next_p,
                        'phase_elapsed': 0,
                        'phase_target': self._get_phase_target(next_p),
                        'actual_level': None
                    }, namespace='/sbr')
                    last_pulse_state = None
                    continue

            if self.phase_elapsed == 0 and phase != 'influent':
                log(f"🔍 Eerste tick van fase {phase}, roep _apply_phase_logic_pumps aan")
                self._apply_phase_logic_pumps(phase)

            log(f"🔍 Emit sbr_timer voor fase {phase}")
            self.socketio.emit('sbr_timer', {
                'timer': self.timer,
                'phase': phase,
                'phase_elapsed': self.phase_elapsed,
                'phase_target': self._get_phase_target(phase),
                'actual_level': actual
            }, namespace='/sbr')

            self.socketio.sleep(1)
            self.phase_elapsed += 1
            self.timer += 1

def start_sbr_controller(socketio: SocketIO):
    global sbr_controller
    sbr_controller = SBRController(socketio)
    threading.Thread(target=sbr_controller.run, daemon=True).start()
