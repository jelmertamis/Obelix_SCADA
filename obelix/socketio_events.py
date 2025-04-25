# obelix/socketio_events.py

from flask_socketio import emit
from obelix.config import Config
from obelix.database import (
    get_calibration, save_calibration, get_aio_setting, save_aio_setting,
    get_relay_state, save_relay_state, get_setting, set_setting, get_all_calibrations
)
from obelix.modbus_client import get_clients, fallback_mode, read_relay_states, modbus_lock
from obelix.utils import log

def init_socketio(socketio):
    @socketio.on('connect', namespace='/relays')
    def ws_relays_connect(auth):
        log("SocketIO: /relays connected")
        clients = get_clients()
        out = []
        for i, unit in enumerate(Config.UNITS):
            if unit['type'] == 'relay':
                try:
                    states = read_relay_states(i)
                    log(f"Relaisstatussen voor unit {i} ({unit['name']}): {states}")
                    for coil in range(8):
                        if not fallback_mode:
                            try:
                                saved_state = get_relay_state(i, coil)
                                actual_state = states[coil]
                                state_str = 'ON' if actual_state else 'OFF'
                                if saved_state is not None and saved_state != state_str:
                                    log(f"⚠️ Relay state mismatch: unit {i}, coil {coil}, saved {saved_state}, actual {state_str}")
                                    save_relay_state(i, coil, state_str)
                                if saved_state is None:
                                    save_relay_state(i, coil, state_str)
                            except Exception as e:
                                log(f"⚠️ Fout bij verwerken relaisstatus unit {i}, coil {coil}: {e}")
                                states[coil] = False
                    out.append({
                        'idx': i,
                        'name': unit['name'],
                        'states': states
                    })
                except Exception as e:
                    log(f"⚠️ Fout bij ophalen relaisstatussen voor unit {i} ({unit['name']}): {e}")
                    out.append({
                        'idx': i,
                        'name': unit['name'],
                        'states': [False] * 8
                    })
        log(f"Verstuur init_relays: {out}")
        emit('init_relays', out, namespace='/relays')

    @socketio.on('toggle_relay', namespace='/relays')
    def ws_toggle_relay(msg):
        try:
            idx = msg['unit_idx']
            coil = msg['coil_idx']
            want = msg['state']
            if not isinstance(idx, int) or idx >= len(get_clients()):
                raise ValueError(f"Ongeldige unit_idx: {idx}")
            if not isinstance(coil, int) or not 0 <= coil < 8:
                raise ValueError(f"Ongeldige coil_idx: {coil}")
            if want not in ('ON', 'OFF'):
                raise ValueError(f"Ongeldige state: {want}")
            log(f"🔄 Relay change requested: unit {idx}, coil {coil} → {want}")
            clients = get_clients()
            inst = clients[idx]
            with modbus_lock:
                if want == 'ON':
                    inst.write_bit(coil, True, functioncode=5)
                else:
                    inst.write_bit(coil, False, functioncode=5)
            save_relay_state(idx, coil, want)
            emit('relay_toggled', {
                'unit_idx': idx,
                'coil_idx': coil,
                'state': want
            }, namespace='/relays', broadcast=True)
            log(f"✅ Relay changed: unit {idx}, coil {coil} is now {want}")
        except Exception as e:
            log(f"⚠️ Modbus error toggling unit {idx}, coil {coil}: {e}")
            emit('relay_error', {'error': str(e)}, namespace='/relays')

    @socketio.on('connect', namespace='/sensors')
    def ws_sensors_connect(auth):
        log("SocketIO: /sensors connected")

    @socketio.on('connect', namespace='/cal')
    def ws_cal_connect(auth):
        log("SocketIO: /cal connected")
        payload = get_all_calibrations()
        emit('init_cal', payload, namespace='/cal')

    @socketio.on('set_cal_points', namespace='/cal')
    def ws_set_cal(msg):
        u, ch = msg['unit'], msg['channel']
        raw1, phys1 = msg['raw1'], msg['phys1']
        raw2, phys2 = msg['raw2'], msg['phys2']
        unit_str = msg.get('unitStr', '')
        try:
            if raw1 == raw2:
                raise ValueError("raw1 en raw2 mogen niet gelijk zijn")
            scale = (phys2 - phys1) / (raw2 - raw1)
            offset = phys1 - scale * raw1
            save_calibration(u, ch, scale, offset, phys1, phys2, unit_str)
            emit('cal_saved', {
                'unit':     u,
                'channel':  ch,
                'scale':    scale,
                'offset':   offset,
                'phys_min': phys1,
                'phys_max': phys2,
                'unitStr':  unit_str
            }, namespace='/cal')
        except Exception as e:
            emit('cal_error', {'error': str(e)}, namespace='/cal')

    @socketio.on('connect', namespace='/aio')
    def ws_aio_connect(auth):
        log("SocketIO: /aio connected")
        clients = get_clients()
        rows = []
        inst = clients[Config.AIO_IDX]
        for ch in range(4):
            try:
                with modbus_lock:
                    raw_out = inst.read_register(ch, functioncode=3)
                phys_out = round((raw_out / 4095.0) * 20.0, 2)
                pct = get_aio_setting(ch)
                if pct is None:
                    pct = round((phys_out - 4.0) / 16.0 * 100.0, 1) if phys_out > 4.0 else None
                rows.append({
                    'channel': ch,
                    'raw_out': raw_out,
                    'phys_out': phys_out,
                    'percent_out': pct
                })
            except Exception as e:
                log(f"⚠️ Error reading AIO channel {ch}: {e}")
                rows.append({
                    'channel': ch,
                    'raw_out': 0,
                    'phys_out': 0.0,
                    'percent_out': get_aio_setting(ch)
                })
        emit('aio_init', rows, namespace='/aio')

    @socketio.on('aio_set', namespace='/aio')
    def ws_aio_set(msg):
        try:
            ch, pct = msg['channel'], float(msg['percent'])
            if not 0 <= ch <= 3:
                raise ValueError(f"Invalid channel: {ch}")
            if not 0 <= pct <= 100:
                raise ValueError(f"Invalid percent: {pct}")
            mA = 4.0 + (pct / 100.0) * 16.0
            raw = int((mA / 20.0) * 4095)
            inst = get_clients()[Config.AIO_IDX]
            with modbus_lock:
                inst.write_register(ch, raw, functioncode=6)
            save_aio_setting(ch, pct)
            emit('aio_updated', {
                'channel':     ch,
                'raw_out':     raw,
                'phys_out':    round(mA, 2),
                'percent_out': pct
            }, namespace='/aio')
            log(f"✅ AIO channel {ch} set to {pct}%")
        except Exception as e:
            log(f"⚠️ Error setting AIO channel {ch}: {e}")
            emit('aio_error', {'error': str(e)}, namespace='/aio')

    @socketio.on('connect', namespace='/r302')
    def ws_r302_connect(auth):
        log("SocketIO: /r302 connected")
        sensors = [{'name': f'Sensor {i+1}', 'raw': None, 'value': None} for i in range(4)]
        pumps = {
            k: get_setting(f'pump_{k}_mode', Config.DEFAULT_PUMP_MODE)
            for k in ('influent', 'nutrient', 'effluent')
        }
        compressors = {
            num: {
                'mode': get_setting(f'compressor{num}_mode', Config.DEFAULT_COMPRESSOR_MODE),
                'freq': float(get_setting(f'compressor{num}_freq', 0.0))
            }
            for num in (1, 2)
        }
        emit('r302_init', {
            'sensors':     sensors,
            'pumps':       pumps,
            'compressors': compressors
        }, namespace='/r302')

    @socketio.on('set_pump_mode', namespace='/r302')
    def ws_set_pump_mode(msg):
        pump, mode = msg['pump'], msg['mode']
        set_setting(f'pump_{pump}_mode', mode)
        emit('pump_mode_updated', {'pump': pump, 'mode': mode}, namespace='/r302', broadcast=True)

    @socketio.on('set_compressor_mode', namespace='/r302')
    def ws_set_compressor_mode(msg):
        num, mode = msg['compressor'], msg['mode']
        set_setting(f'compressor{num}_mode', mode)
        emit('compressor_mode_updated', {'compressor': num, 'mode': mode}, namespace='/r302', broadcast=True)

    @socketio.on('set_compressor_freq', namespace='/r302')
    def ws_set_compressor_freq(msg):
        num, freq = msg['compressor'], float(msg['freq'])
        set_setting(f'compressor{num}_freq', freq)
        emit('compressor_freq_updated', {'compressor': num, 'freq': freq}, namespace='/r302', broadcast=True)
