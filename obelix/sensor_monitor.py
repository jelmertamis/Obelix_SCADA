import time
from obelix.config import Config
from obelix.database import get_calibration
from obelix.modbus_client import get_clients, modbus_lock, modbus_initialized
from obelix.utils import log

def start_sensor_monitor(socketio):
    modbus_initialized.wait()  # Wacht tot Modbus is geïnitialiseerd
    log("Sensor_monitor gestart")
    while True:
        data = []
        clients = get_clients()
        if not clients:
            log("⚠️ Geen Modbus-clients beschikbaar, sensor ELA_monitor overslaan")
            time.sleep(1)
            continue
        for i, unit in enumerate(Config.UNITS):
            if unit['type'] == 'analog':
                if i >= len(clients):
                    log(f"⚠️ Index {i} buiten bereik van clients (lengte: {len(clients)})")
                    continue
                inst = clients[i]
                for ch in range(4):
                    try:
                        with modbus_lock:
                            raw = inst.read_register(ch, functioncode=4)
                        cal = get_calibration(i, ch)
                        val = raw * cal['scale'] + cal['offset']
                        data.append({
                            'name': unit['name'],
                            'slave_id': unit['slave_id'],
                            'channel': ch,
                            'raw': raw,
                            'value': round(val, 2)
                        })
                    except Exception as e:
                        log(f"⚠️ Error reading sensor {unit['name']} channel {ch}: {e}")
        socketio.emit('sensor_update', data, namespace='/sensors')
        time.sleep(1)