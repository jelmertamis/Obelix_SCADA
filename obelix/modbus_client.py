import minimalmodbus
from threading import Lock, Event
from obelix.config import Config
from obelix.utils import log
from obelix.database import get_relay_state

modbus_lock = Lock()
clients = []
fallback_mode = False
modbus_initialized = Event()  # Voor synchronisatie

class DummyModbusClient:
    def __init__(self, *args, **kwargs):
        self._ctr = 0
    def read_bit(self, coil, functioncode=None):
        self._ctr += 1
        return (self._ctr % 2) == 0
    def write_bit(self, coil, state, functioncode=None): pass
    def read_register(self, reg, functioncode=None):
        self._ctr += 1
        return (self._ctr * 137) % 4096
    def write_register(self, reg, value, functioncode=None): pass

def init_modbus():
    global clients, fallback_mode
    clients = []
    log(f"Initialiseren van Modbus voor {len(Config.UNITS)} units")
    if not Config.UNITS:
        log("⚠️ Config.UNITS is leeg! Geen Modbus-clients worden geïnitialiseerd.")
        fallback_mode = True
        modbus_initialized.set()
        return
    try:
        for unit in Config.UNITS:
            inst = minimalmodbus.Instrument(Config.RS485_PORT, unit['slave_id'], mode=minimalmodbus.MODE_RTU)
            inst.serial.baudrate = Config.BAUDRATE
            inst.serial.parity = Config.PARITY
            inst.serial.stopbits = Config.STOPBITS
            inst.serial.bytesize = Config.BYTESIZE
            inst.serial.timeout = Config.TIMEOUT
            inst.clear_buffers_before_each_transaction = True

            with modbus_lock:
                if unit['type'] == 'relay':
                    inst.read_bit(0, functioncode=1)
                else:
                    inst.read_register(0, functioncode=4)

            clients.append(inst)
            log(f"Modbus OK voor {unit['name']} (ID {unit['slave_id']})")
        fallback_mode = False
    except Exception as e:
        log(f"Modbus niet gevonden ({e}), overschakelen naar Dummy‐modus.")
        clients = [DummyModbusClient() for _ in Config.UNITS]
        fallback_mode = True
    log(f"Modbus-initialisatie voltooid: {len(clients)} clients geïnitialiseerd")
    modbus_initialized.set()  # Signaleer dat initialisatie voltooid is

def get_clients():
    return clients

def read_relay_states(idx):
    if idx >= len(clients):
        log(f"⚠️ Ongeldige unit-index {idx}, geen client beschikbaar")
        return [False] * 8
    inst = clients[idx]
    if fallback_mode:
        states = []
        for coil in range(8):
            saved_state = get_relay_state(idx, coil)
            states.append(saved_state == 'ON' if saved_state else False)
        return states
    with modbus_lock:
        try:
            bits = inst.read_bits(0, 8, functioncode=1)
        except Exception:
            bits = []
            for coil in range(8):
                try:
                    bits.append(inst.read_bit(coil, functioncode=1))
                except:
                    bits.append(False)
        return bits