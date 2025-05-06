# obelix/socketio_events.py

from flask_socketio import emit
from obelix.config import Config
from obelix.database import (
    get_setting, set_setting, get_all_calibrations,
    get_relay_state, save_relay_state,
    get_calibration, save_calibration,
    get_dummy_value, get_aio_setting
)
from obelix.modbus_client import (
    get_clients, fallback_mode,
    read_relay_states, modbus_lock
)
from obelix.utils import log
from obelix.r302_manager import R302Controller
from obelix import auto_control

r302_ctrl = R302Controller(unit_index=0)

def init_socketio(socketio):
    # ----- RELAYS -----
    @socketio.on('connect', namespace='/relays')
    def ws_relays_connect(auth):
        log("SocketIO: /relays connected")
        out = []
        clients = get_clients()
        for i, unit in enumerate(Config.UNITS):
            if unit['type'] == 'relay':
                try:
                    states = read_relay_states(i)
                    if not fallback_mode:
                        for coil, actual in enumerate(states):
                            state_str = 'ON' if actual else 'OFF'
                            if get_relay_state(i, coil) != state_str:
                                save_relay_state(i, coil, state_str)
                    item = {'idx': i, 'name': unit['name'], 'states': states}
                    if i == r302_ctrl.unit:
                        item['modes'] = [r302_ctrl.get_mode(c) for c in range(len(states))]
                    out.append(item)
                except Exception as e:
                    log(f"Error fetching relays unit {i}: {e}")
                    out.append({'idx': i, 'name': unit['name'], 'states': [False]*8})
        emit('init_relays', out, namespace='/relays')
    
    def broadcast_phase_settings(ctrl):
        """Stuur álle thresholds en tijden naar de client."""
        emit('sbr_phase_times', {
            'influent_threshold': float(get_setting('sbr_influent_level_threshold', '0')),
            'effluent_threshold': float(get_setting('sbr_effluent_level_threshold', '0')),
            'react_minutes':      ctrl.react_time,
            'react_seconds':      ctrl._get_phase_target('react'),
            'wait_minutes':       ctrl.wait_time,
            'wait_seconds':       ctrl._get_phase_target('wait'),
            'dose_nutrients_minutes': ctrl.dose_time,
            'dose_nutrients_seconds': int(ctrl.dose_time * 60),
            'wait_after_N_minutes':   ctrl.wait_after_N_time,
            'wait_after_N_seconds':   int(ctrl.wait_after_N_time * 60),
            'cycle_time_max_minutes': ctrl.cycle_time_max,
            'heating_on_temp':  ctrl.heat_on_temp,
            'heating_off_temp':  ctrl.heat_off_temp,
        }, namespace='/sbr')


    @socketio.on('toggle_relay', namespace='/relays')
    def ws_toggle_relay(msg):
        idx, coil, want = msg['unit_idx'], msg['coil_idx'], msg['state']
        try:
            inst = get_clients()[idx]
            with modbus_lock:
                inst.write_bit(coil, want == 'ON', functioncode=5)
            save_relay_state(idx, coil, want)
            emit('relay_toggled',
                 {'unit_idx': idx, 'coil_idx': coil, 'state': want},
                 namespace='/relays', broadcast=True)
        except Exception as e:
            log(f"Error toggling relay {idx}/{coil}: {e}")
            emit('relay_error', {'error': str(e)}, namespace='/relays')

    # ----- SENSORS -----
    @socketio.on('connect', namespace='/sensors')
    def ws_sensors_connect(auth):
        log("SocketIO: /sensors connected")

    # ----- CALIBRATION -----
    @socketio.on('connect', namespace='/cal')
    def ws_cal_connect(auth):
        log("SocketIO: /cal connected")
        emit('init_cal', get_all_calibrations(), namespace='/cal')

    @socketio.on('set_cal_points', namespace='/cal')
    def ws_set_cal(msg):
        try:
            u, ch = msg['unit'], msg['channel']
            raw1, phys1 = msg['raw1'], msg['phys1']
            raw2, phys2 = msg['raw2'], msg['phys2']
            unitStr = msg.get('unitStr', '')
            if raw1 == raw2:
                raise ValueError("raw1 en raw2 mogen niet gelijk zijn")
            scale = (phys2 - phys1) / (raw2 - raw1)
            offset = phys1 - scale * raw1
            save_calibration(u, ch, scale, offset, phys1, phys2, unitStr)
            emit('cal_saved', {
                'unit': u, 'channel': ch,
                'scale': scale, 'offset': offset,
                'phys_min': phys1, 'phys_max': phys2,
                'unitStr': unitStr
            }, namespace='/cal')
        except Exception as e:
            emit('cal_error', {'error': str(e)}, namespace='/cal')

    # ----- AIO -----
    @socketio.on('connect', namespace='/aio')
    def ws_aio_connect(auth):
        log("SocketIO: /aio connected")
        rows = []
        inst = get_clients()[Config.AIO_IDX]
        ctrl = auto_control.sbr_controller  # Haal de SBRController-instantie op
        current_phase = ctrl.current_phase if ctrl else 'influent'  # Fallback naar influent

        for ch in range(2):  # Alleen kanalen 0 (K303) en 1 (K304)
            try:
                with modbus_lock:
                    raw_out = inst.read_register(ch, functioncode=3)
                phys_out = round((raw_out / 4095.0) * 20.0, 2)
                # Haal de actuele percentage-instelling op voor de huidige fase
                k = 'k303' if ch == 0 else 'k304'
                pct = float(get_setting(f'compressor_{current_phase}_{k}_pct', '0'))
                rows.append({
                    'channel': ch,
                    'raw_out': raw_out,
                    'phys_out': phys_out,
                    'percent_out': pct
                })
            except Exception as e:
                log(f"Error reading AIO ch{ch}: {e}")
                rows.append({
                    'channel': ch,
                    'raw_out': 0,
                    'phys_out': 0.0,
                    'percent_out': None
                })
        emit('aio_init', rows, namespace='/aio')


    @socketio.on('aio_set', namespace='/aio')
    def ws_aio_set(msg):
        try:
            ch, pct = msg['channel'], float(msg['percent'])
            mA = 4.0 + pct/100.0*16.0
            raw = int((mA/20.0)*4095)
            inst = get_clients()[Config.AIO_IDX]
            with modbus_lock:
                inst.write_register(ch, raw, functioncode=6)
            set_setting(f'aio_setting_{ch}', pct)
            emit('aio_updated', {
                'channel': ch,
                'raw_out': raw,
                'phys_out': round(mA, 2),
                'percent_out': pct
            }, namespace='/aio')
        except Exception as e:
            emit('aio_error', {'error': str(e)}, namespace='/aio')

    # ----- R302 REACTOR -----
    @socketio.on('connect', namespace='/r302')
    def ws_r302_connect(auth):
        log("SocketIO: /r302 connected")
        emit('r302_init', r302_ctrl.get_status(), namespace='/r302')

        @socketio.on('set_mode', namespace='/r302')
        def ws_set_mode(msg):
            coil, mode = msg['coil'], msg['mode']
            r302_ctrl.set_mode(coil, mode)
            inst = get_clients()[r302_ctrl.unit]
            if mode in ('MANUAL_ON', 'MANUAL_OFF'):
                want = (mode == 'MANUAL_ON')
                with modbus_lock:
                    inst.write_bit(coil, want, functioncode=5)
                    save_relay_state(r302_ctrl.unit, coil, 'ON' if want else 'OFF')
                emit('relay_toggled',
                     {'unit_idx': r302_ctrl.unit, 'coil_idx': coil, 'state': 'ON' if want else 'OFF'},
                     namespace='/relays', broadcast=True)
                emit('r302_update', r302_ctrl.get_status(), namespace='/r302', broadcast=True)
                return
            emit('r302_update', r302_ctrl.get_status(), namespace='/r302', broadcast=True)
            ctrl = auto_control.sbr_controller
            if ctrl and ctrl.start_event.is_set():
                if ctrl.current_phase in ('react', 'wait'):
                    ctrl._auto_off_all()
                else:
                    ctrl._apply_phase_logic_pumps(ctrl.current_phase)

    # ----- SBR CYCLE -----
    @socketio.on('connect', namespace='/sbr')
    def ws_sbr_connect(auth):
        log("SocketIO: /sbr connected")
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return

        # 1) Start/stop-status
        emit('sbr_status', {'active': ctrl.start_event.is_set()}, namespace='/sbr')

        # 2) Huidige timer en phase (zonder actual_level)
        phase = ctrl.current_phase or 'influent'
        emit('sbr_timer', {
            'timer':         ctrl.timer,
            'phase':         phase,
            'phase_elapsed': ctrl.phase_elapsed,
            'phase_target':  ctrl._get_phase_target(phase),
            'actual_level':  None
        }, namespace='/sbr')

        # 3) Setpoints & threshold
        broadcast_phase_settings(ctrl)

    @socketio.on('sbr_get_phase_times', namespace='/sbr')
    def ws_sbr_get_phase_times():
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return
        broadcast_phase_settings(ctrl)

    @socketio.on('sbr_control', namespace='/sbr')
    def ws_sbr_control(msg):
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return

        action = msg.get('action')
        if action == 'toggle':
            if ctrl.start_event.is_set():
                # Stoppen
                ctrl.stop()
            else:
                # Starten
                ctrl.start()

            # Éénmalig status + fase sturen
            emit('sbr_status', {
                'active': ctrl.start_event.is_set(),
                'phase':  ctrl.current_phase,
                'phase_elapsed': ctrl.phase_elapsed
            }, namespace='/sbr')

            # En direct de thresholds/tijden meezenden
            broadcast_phase_settings(ctrl)
            
        elif action == 'reset':
            ctrl.reset()

            emit('sbr_status', {
                'active': ctrl.start_event.is_set(),
                'phase':  ctrl.current_phase
            }, namespace='/sbr')
            broadcast_phase_settings(ctrl)
        else:
            emit('sbr_error', {'error': f'Unknown action: {action}'}, namespace='/sbr')


    @socketio.on('sbr_set_phase_times', namespace='/sbr')
    def ws_sbr_set_phase_times(msg):
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return
        try:
            updates = {}
            for key in ('react','wait','dose_nutrients','wait_after_N'):
                if key in msg:
                    v = float(msg[key])
                    if v < 0:
                        raise ValueError(f"Tijd voor {key} moet ≥ 0 zijn")
                    updates[key] = v
            ctrl.set_phase_times(
                updates.get('react',    ctrl.react_time),
                updates.get('wait',     ctrl.wait_time),
                updates.get('dose_nutrients', ctrl.dose_time),
                updates.get('wait_after_N', ctrl.wait_after_N_time)

            )
            broadcast_phase_settings(ctrl)
        except Exception as e:
            emit('sbr_error', {'error': str(e)}, namespace='/sbr')

    @socketio.on('sbr_set_threshold', namespace='/sbr')
    def ws_sbr_set_threshold(msg):
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return
        try:
            val = float(msg.get('threshold', 0))
            if val < 0:
                raise ValueError("Threshold moet ≥ 0 zijn")
            set_setting('sbr_influent_level_threshold', str(val))
            ctrl.influent_threshold = val
            broadcast_phase_settings(ctrl)
        except Exception as e:
            emit('sbr_error', {'error': str(e)}, namespace='/sbr')

    @socketio.on('sbr_set_effluent_threshold', namespace='/sbr')
    def ws_sbr_set_effluent_threshold(msg):
        ctrl = auto_control.sbr_controller
        if not ctrl:
            return emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
        try:
            val = float(msg.get('threshold', 0))
            if val < 0:
                raise ValueError("Threshold moet ≥ 0 zijn")
            set_setting('sbr_effluent_level_threshold', str(val))
            ctrl.effluent_threshold = val
            # Gebruik hier dezelfde helper als voor influent!
            broadcast_phase_settings(ctrl)
        except Exception as e:
            emit('sbr_error', {'error': str(e)}, namespace='/sbr')

    @socketio.on('sbr_set_cycle_time_max', namespace='/sbr')
    def ws_sbr_set_cycle_time_max(msg):
        val = float(msg.get('max_minutes', 0))
        set_setting('sbr_cycle_time_max_minutes', str(val))
        ctrl = auto_control.sbr_controller
        ctrl.cycle_time_max = val
        broadcast_phase_settings(ctrl)

    @socketio.on('sbr_set_heating_setpoints', namespace='/sbr')
    def ws_sbr_set_heating_setpoints(msg):
        try:
            on_t  = float(msg.get('on_temp',  0))
            off_t = float(msg.get('off_temp', 0))
            if off_t < on_t:
                raise ValueError("Off-temp mag niet hoger dan on-temp zijn")
            set_setting('heating_valve_on_temp',  str(on_t))
            set_setting('heating_valve_off_temp', str(off_t))
            ctrl = auto_control.sbr_controller
            ctrl.heat_on_temp  = on_t
            ctrl.heat_off_temp = off_t
            broadcast_phase_settings(ctrl)
        except Exception as e:
            emit('sbr_error', {'error': str(e)}, namespace='/sbr')

    @socketio.on('set_compressor_settings', namespace='/sbr')
    def ws_set_compressor_setting(msg):
        """
        Verwacht msg = {
        phase: { k303_on, k303_pct, k304_on, k304_pct },
        …
        }
        """
        log(f"📥 Ontvangen set_compressor_settings: {msg}")
        try:
            for phase, cfg in msg.items():
                set_setting(f'compressor_{phase}_k303_mode', cfg['k303_on'])
                set_setting(f'compressor_{phase}_k303_pct',  cfg['k303_pct'])
                set_setting(f'compressor_{phase}_k304_mode', cfg['k304_on'])
                set_setting(f'compressor_{phase}_k304_pct',  cfg['k304_pct'])
            emit('compressor_updated', msg, namespace='/sbr')
        except Exception as e:
            emit('sbr_error',
                {'error': f"Compressorsetting mislukt: {e}"},
                namespace='/sbr')


    @socketio.on('get_compressor_settings', namespace='/sbr')
    def ws_get_compressor_settings():
        """
        Haal alle compressor-instellingen per phase uit de DB.
        Keys in settings.db: compressor_<phase>_k303_mode, compressor_<phase>_k303_pct, etc.
        """
        phases = ['influent','react','effluent','wait','dose_nutrients','wait_after_N']
        payload = {}
        for phase in phases:
            cfg = {}
            # modes: 'ON' of 'OFF'
            cfg['k303_on']  = get_setting(f'compressor_{phase}_k303_mode', 'OFF')
            cfg['k303_pct'] = float(get_setting(f'compressor_{phase}_k303_pct', '0'))
            cfg['k304_on']  = get_setting(f'compressor_{phase}_k304_mode', 'OFF')
            cfg['k304_pct'] = float(get_setting(f'compressor_{phase}_k304_pct', '0'))
            payload[phase] = cfg
        emit('compressor_settings', payload, namespace='/sbr')

