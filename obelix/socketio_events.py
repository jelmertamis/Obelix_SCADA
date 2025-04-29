# obelix/socketio_events.py

from flask_socketio import emit
from obelix.config import Config
from obelix.database import (
    get_calibration, save_calibration,
    get_aio_setting, save_aio_setting,
    get_relay_state, save_relay_state,
    get_setting, set_setting, get_all_calibrations
)
from obelix.modbus_client import (
    get_clients, fallback_mode, read_relay_states, modbus_lock
)
from obelix.utils import log
from obelix.r302_manager import R302Controller
from obelix import auto_control

r302_ctrl = R302Controller(unit_index=0)

def init_socketio(socketio):
    # ----- Relays namespace -----
    @socketio.on('connect', namespace='/relays')
    def ws_relays_connect(auth):
        log("SocketIO: /relays connected")
        out = []
        clients = get_clients()
        for i, unit in enumerate(Config.UNITS):
            if unit['type'] == 'relay':
                try:
                    states = read_relay_states(i)
                    for coil, actual in enumerate(states):
                        if not fallback_mode:
                            saved = get_relay_state(i, coil)
                            state_str = 'ON' if actual else 'OFF'
                            if saved != state_str:
                                save_relay_state(i, coil, state_str)
                    item = {'idx': i, 'name': unit['name'], 'states': states}
                    if i == r302_ctrl.unit:
                        item['modes'] = [r302_ctrl.get_mode(c) for c in range(len(states))]
                    out.append(item)
                except Exception as e:
                    log(f"Error relays unit {i}: {e}")
                    out.append({'idx': i, 'name': unit['name'], 'states': [False]*8})
        emit('init_relays', out, namespace='/relays')

    @socketio.on('toggle_relay', namespace='/relays')
    def ws_toggle_relay(msg):
        try:
            idx, coil, want = msg['unit_idx'], msg['coil_idx'], msg['state']
            inst = get_clients()[idx]
            with modbus_lock:
                inst.write_bit(coil, want=='ON', functioncode=5)
            save_relay_state(idx, coil, want)
            emit('relay_toggled', {'unit_idx': idx, 'coil_idx': coil, 'state': want},
                 namespace='/relays', broadcast=True)
        except Exception as e:
            emit('relay_error', {'error': str(e)}, namespace='/relays')

    # ----- Sensors namespace -----
    @socketio.on('connect', namespace='/sensors')
    def ws_sensors_connect(auth):
        log("SocketIO: /sensors connected")

    # ----- Calibration namespace -----
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
            if raw1 == raw2:
                raise ValueError("raw1 en raw2 mogen niet gelijk zijn")
            scale = (phys2 - phys1) / (raw2 - raw1)
            offset = phys1 - scale * raw1
            save_calibration(u, ch, scale, offset, phys1, phys2, msg.get('unitStr', ''))
            emit('cal_saved', {
                'unit': u, 'channel': ch,
                'scale': scale, 'offset': offset,
                'phys_min': phys1, 'phys_max': phys2,
                'unitStr': msg.get('unitStr', '')
            }, namespace='/cal')
        except Exception as e:
            emit('cal_error', {'error': str(e)}, namespace='/cal')

    # ----- AIO namespace -----
    @socketio.on('connect', namespace='/aio')
    def ws_aio_connect(auth):
        log("SocketIO: /aio connected")
        rows = []
        inst = get_clients()[Config.AIO_IDX]
        for ch in range(4):
            try:
                with modbus_lock:
                    raw_out = inst.read_register(ch, functioncode=3)
                phys_out = round((raw_out / 4095) * 20.0, 2)
                pct = get_aio_setting(ch)
                rows.append({
                    'channel': ch, 'raw_out': raw_out,
                    'phys_out': phys_out, 'percent_out': pct
                })
            except Exception as e:
                rows.append({
                    'channel': ch, 'raw_out': 0,
                    'phys_out': 0.0, 'percent_out': get_aio_setting(ch)
                })
        emit('aio_init', rows, namespace='/aio')

    @socketio.on('aio_set', namespace='/aio')
    def ws_aio_set(msg):
        try:
            ch, pct = msg['channel'], float(msg['percent'])
            mA = 4.0 + pct/100.0 * 16.0
            raw = int(mA/20.0 * 4095)
            inst = get_clients()[Config.AIO_IDX]
            with modbus_lock:
                inst.write_register(ch, raw, functioncode=6)
            save_aio_setting(ch, pct)
            emit('aio_updated', {
                'channel': ch, 'raw_out': raw,
                'phys_out': round(mA,2), 'percent_out': pct
            }, namespace='/aio')
        except Exception as e:
            emit('aio_error', {'error': str(e)}, namespace='/aio')

    # ----- R302 Reactor namespace -----
    @socketio.on('connect', namespace='/r302')
    def ws_r302_connect(auth):
        log("SocketIO: /r302 connected")
        emit('r302_init', r302_ctrl.get_status(), namespace='/r302')

    @socketio.on('set_mode', namespace='/r302')
    def ws_set_mode(msg):
        r302_ctrl.set_mode(msg['coil'], msg['mode'])
        emit('r302_update', r302_ctrl.get_status(), namespace='/r302', broadcast=True)

    # ----- SBR namespace -----
    @socketio.on('connect', namespace='/sbr')
    def ws_sbr_connect(auth):
        log("SocketIO: /sbr connected")
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return
        emit('sbr_status', {'active': ctrl.start_event.is_set()}, namespace='/sbr')
        emit('sbr_timer', {'timer': ctrl.timer}, namespace='/sbr')
        ctrl._emit_phase_times()  # direct de opgeslagen tijden

    @socketio.on('sbr_control', namespace='/sbr')
    def ws_sbr_control(msg):
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return
        action = msg.get('action')
        if action == 'toggle':
            ctrl.stop() if ctrl.start_event.is_set() else ctrl.start()
        elif action == 'reset':
            ctrl.reset()
        else:
            emit('sbr_error', {'error': f'Unknown action: {action}'}, namespace='/sbr')

    @socketio.on('sbr_set_phase_times', namespace='/sbr')
    def ws_sbr_set_phase_times(msg):
        ctrl = auto_control.sbr_controller
        if not ctrl:
            emit('sbr_error', {'error': 'No SBR controller'}, namespace='/sbr')
            return
        try:
            infl = float(msg['influent'])
            effl = float(msg['effluent'])
            if infl <= 0 or effl <= 0:
                raise ValueError("Tijden moeten groter dan 0 zijn")
            ctrl.set_phase_times(infl, effl)
        except Exception as e:
            emit('sbr_error', {'error': str(e)}, namespace='/sbr')

    @socketio.on('sbr_get_phase_times', namespace='/sbr')
    def ws_sbr_get_phase_times():
        """Verzend de laatst opgeslagen fasetijden naar de client."""
        ctrl = auto_control.sbr_controller
        if ctrl:
            ctrl._emit_phase_times()
