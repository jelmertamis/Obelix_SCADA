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
                    states = read_relay_relay_states(i) if False else read_relay_states(i)  # typo guard
                    log(f"Relaisstatussen voor unit {i} ({unit['name']}): {states}")
                    for coil in range(8):
                        if not fallback_mode:
                            saved = get_relay_state(i, coil)
                            actual = states[coil]
                            state_str = 'ON' if actual else 'OFF'
                            if saved is None or saved != state_str:
                                save_relay_state(i, coil, state_str)
                    out.append({
                        'idx':    i,
                        'name':   unit['name'],
                        'states': states
                    })
                except Exception as e:
                    log(f"⚠ Fout bij ophalen relaisstatus unit {i} ({unit['name']}): {e}")
                    out.append({
                        'idx':    i,
                        'name':   unit['name'],
                        'states': [False]*8
                    })
        emit('init_relays', out, namespace='/relays')

    @socketio.on('toggle_relay', namespace='/relays')
    def ws_toggle_relay(msg):
        try:
            idx   = msg['unit_idx']
            coil  = msg['coil_idx']
            want  = msg['state']
            clients = get_clients()
            if idx < 0 or idx >= len(clients):
                raise ValueError(f"Ongeldige unit_idx: {idx}")
            if coil < 0 or coil >= 8:
                raise ValueError(f"Ongeldige coil_idx: {coil}")
            if want not in ('ON','OFF'):
                raise ValueError(f"Ongeldige state: {want}")
            log(f"🔄 Relay change requested: unit {idx}, coil {coil} → {want}")
            inst = clients[idx]
            with modbus_lock:
                inst.write_bit(coil, want=='ON', functioncode=5)
            save_relay_state(idx, coil, want)
            emit('relay_toggled', {
                'unit_idx': idx,
                'coil_idx': coil,
                'state':    want
            }, namespace='/relays', broadcast=True)
            log(f"✅ Relay changed: unit {idx}, coil {coil} is now {want}")
        except Exception as e:
            log(f"⚠ Modbus error toggling unit {idx}, coil {coil}: {e}")
            emit('relay_error', {'error': str(e)}, namespace='/relays')

    # ----- Sensors namespace -----
    @socketio.on('connect', namespace='/sensors')
    def ws_sensors_connect(auth):
        log("SocketIO: /sensors connected")

    # ----- Calibration namespace -----
    @socketio.on('connect', namespace='/cal')
    def ws_cal_connect(auth):
        log("SocketIO: /cal connected")
        payload = get_all_calibrations()
        emit('init_cal', payload, namespace='/cal')

    @socketio.on('set_cal_points', namespace='/cal')
    def ws_set_cal(msg):
        try:
            u, ch   = msg['unit'], msg['channel']
            raw1    = msg['raw1']; phys1 = msg['phys1']
            raw2    = msg['raw2']; phys2 = msg['phys2']
            unitStr = msg.get('unitStr', '')
            if raw1 == raw2:
                raise ValueError("raw1 en raw2 mogen niet gelijk zijn")
            scale  = (phys2 - phys1) / (raw2 - raw1)
            offset = phys1 - scale * raw1
            save_calibration(u, ch, scale, offset, phys1, phys2, unitStr)
            emit('cal_saved', {
                'unit':     u,
                'channel':  ch,
                'scale':    scale,
                'offset':   offset,
                'phys_min': phys1,
                'phys_max': phys2,
                'unitStr':  unitStr
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
                phys_out = round((raw_out/4095.0)*20.0, 2)
                pct = get_aio_setting(ch)
                if pct is None:
                    pct = round((phys_out - 4.0)/16.0*100.0,1) if phys_out > 4.0 else None
                rows.append({
                    'channel':     ch,
                    'raw_out':     raw_out,
                    'phys_out':    phys_out,
                    'percent_out': pct
                })
            except Exception as e:
                log(f"⚠ Error reading AIO channel {ch}: {e}")
                rows.append({
                    'channel':     ch,
                    'raw_out':     0,
                    'phys_out':    0.0,
                    'percent_out': get_aio_setting(ch)
                })
        emit('aio_init', rows, namespace='/aio')

    @socketio.on('aio_set', namespace='/aio')
    def ws_aio_set(msg):
        try:
            ch  = msg['channel']
            pct = float(msg['percent'])
            if not 0 <= pct <= 100:
                raise ValueError(f"Invalid percent: {pct}")
            mA = 4.0 + (pct/100.0)*16.0
            raw = int((mA/20.0)*4095)
            inst = get_clients()[Config.AIO_IDX]
            with modbus_lock:
                inst.write_register(ch, raw, functioncode=6)
            save_aio_setting(ch, pct)
            emit('aio_updated', {
                'channel':     ch,
                'raw_out':     raw,
                'phys_out':    round(mA,2),
                'percent_out': pct
            }, namespace='/aio')
            log(f"✅ AIO channel {ch} set to {pct}%")
        except Exception as e:
            log(f"⚠ Error setting AIO channel {ch}: {e}")
            emit('aio_error', {'error': str(e)}, namespace='/aio')

    # ----- R302 Reactor namespace -----
    @socketio.on('connect', namespace='/r302')
    def ws_r302_connect(auth):
        log("SocketIO: /r302 connected")

        # Sensors
        sensors = []
        for ch, label in Config.R302_SENSOR_MAPPING.items():
            sensors.append({
                'channel': ch,
                'label':   label,
                'raw':     None,
                'value':   None,
                'unit':    ''
            })

        # Pumps (relays 0-2)
        pumps = {}
        for coil in (0,1,2):
            label = Config.R302_RELAY_MAPPING[coil]
            mode  = get_setting(f'pump_{coil}_mode', Config.DEFAULT_PUMP_MODE)
            pumps[coil] = {'label': label, 'mode': mode}

        # Compressors ON/OFF (relays 3-4) + frequency
        compressors = {}
        for coil in (3,4):
            label = Config.R302_RELAY_MAPPING[coil]
            mode  = get_setting(f'compressor{coil}_mode', Config.DEFAULT_COMPRESSOR_MODE)
            freq  = float(get_setting(f'compressor{coil}_freq', 0.0))
            compressors[coil] = {'label': label, 'mode': mode, 'freq': freq}

        # Analog outputs
        aio = []
        for ch, label in Config.R302_AIO_MAPPING.items():
            pct = get_setting(f'aio_{ch}_percent', None)
            aio.append({'channel': ch, 'label': label, 'percent_out': pct})

        emit('r302_init', {
            'sensors':     sensors,
            'pumps':       pumps,
            'compressors': compressors,
            'aio':         aio
        }, namespace='/r302')

    @socketio.on('set_pump_mode', namespace='/r302')
    def ws_set_pump_mode(msg):
        pump = msg['pump']
        mode = msg['mode']
        set_setting(f'pump_{pump}_mode', mode)
        emit('pump_mode_updated', {'pump': pump, 'mode': mode}, namespace='/r302', broadcast=True)

    @socketio.on('set_compressor_mode', namespace='/r302')
    def ws_set_compressor_mode(msg):
        comp = msg['compressor']
        mode = msg['mode']
        set_setting(f'compressor{comp}_mode', mode)
        emit('compressor_mode_updated', {'compressor': comp, 'mode': mode}, namespace='/r302', broadcast=True)

    @socketio.on('set_compressor_freq', namespace='/r302')
    def ws_set_compressor_freq(msg):
        comp = msg['compressor']
        freq = float(msg['freq'])
        set_setting(f'compressor{comp}_freq', freq)
        emit('compressor_freq_updated', {'compressor': comp, 'freq': freq}, namespace='/r302', broadcast=True)
