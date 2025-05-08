# obelix/sensor_monitor.py

import time
import threading
from collections import defaultdict
from obelix.config import Config
from obelix.database import get_calibration, get_dummy_value
from obelix.sensor_database import save_sensor_reading
import obelix.modbus_client as modbus_client

from obelix.utils import log
from obelix.influx_integration import write_sensor_reading      # <<<  NIEUW

def start_sensor_monitor(socketio):
    log(f"Sensor_monitor gestart: live={Config.LIVE_POLL_INTERVAL}s, store={Config.STORAGE_INTERVAL}s")

    buffer = defaultdict(list)
    stop_event = threading.Event()

    def storage_worker():
        while not stop_event.is_set():
            time.sleep(Config.STORAGE_INTERVAL)
            for (i, ch), vals in list(buffer.items()):
                if vals:
                    avg = sum(vals) / len(vals)
                    save_sensor_reading(i, ch, None, avg, '')
            buffer.clear()
            log("✔ Sensor data opgeslagen (gepoold gemiddelde)")

    threading.Thread(target=storage_worker, daemon=True).start()

    while True:
        # log("SENSOR MONITOR tick...")
        start = time.time()
        data = []
        clients = modbus_client.get_clients()
        if not clients:
            log("⚠ Geen Modbus-clients, overslaan live-update")
        else:
            for i, unit in enumerate(Config.UNITS):
                if unit['type'] == 'analog' and i < len(clients):
                    inst = clients[i]
                    for ch in range(4):
                        try:
                            # Eerst handmatig ingestelde dummy-waarde ophalen
                            dummy = get_dummy_value(i, ch)
                            if dummy is not None:
                                raw = dummy
                            else:
                                with modbus_client.modbus_lock:
                                    raw = inst.read_register(ch, functioncode=4)

                            cal = get_calibration(i, ch)
                            val = raw * cal['scale'] + cal['offset']
                            buffer[(i, ch)].append(val)
                            data.append({
                                'name':     unit['name'],
                                'slave_id': unit['slave_id'],
                                'channel':  ch,
                                'raw':      raw,
                                'value':    round(val, 2),
                                'unit':     cal.get('unit', '')
                            })

                            # -------------  NIEUW: schrijf direct naar InfluxDB
                            # log(f"fallback {modbus_client.fallback_mode}")
                            if not modbus_client.fallback_mode:
                                write_sensor_reading(i, ch, val)
                            # -------------------------------------------------

                        except Exception as e:
                            log(f"⚠ Error reading {unit['name']} ch{ch}: {e}")
        # log(f"Emitting SENSOR update {len(data)} readings")
        socketio.emit('sensor_update', data, namespace='/sensors')
        elapsed = time.time() - start
        time.sleep(max(0, Config.LIVE_POLL_INTERVAL - elapsed))
