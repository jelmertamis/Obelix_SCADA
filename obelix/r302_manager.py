# obelix/r302_manager.py

from obelix.config import Config
from obelix.database import get_setting, set_setting
from obelix.modbus_client import read_relay_states

class R302Controller:
    def __init__(self, unit_index=0):
        self.unit = unit_index
        # laadt per coil de mode uit settings.db, default = AUTO
        self.modes = {
            coil: get_setting(f'r302_relay_{coil}_mode', 'AUTO')
            for coil in Config.R302_RELAY_MAPPING
        }

    def get_mode(self, coil):
        return self.modes.get(coil, 'AUTO')

    def set_mode(self, coil, mode):
        assert mode in ('AUTO','MANUAL_ON','MANUAL_OFF'), f"Onbekende mode: {mode}"
        # bewaar in DB
        set_setting(f'r302_relay_{coil}_mode', mode)
        self.modes[coil] = mode

    def get_status(self):
        """
        Retourneert dict:
          { coil_index: { 'mode': <AUTO|MANUAL_ON|MANUAL_OFF>,
                          'physical': <bool> } }
        """
        physical_states = read_relay_states(self.unit)
        status = {}
        for coil in Config.R302_RELAY_MAPPING:
            physical = physical_states[coil]
            status[coil] = {
                'mode':     self.get_mode(coil),
                'physical': physical
            }
        return status
