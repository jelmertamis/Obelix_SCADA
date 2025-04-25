from flask import render_template
from obelix.config import Config
from obelix.modbus_client import fallback_mode

def init_routes(app):
    @app.route('/')
    def index():
        return render_template('dashboard.html', fallback_mode=fallback_mode)

    @app.route('/relays')
    def relays():
        relay_units = []
        for i, unit in enumerate(Config.UNITS):
            if unit['type'] == 'relay':
                relay_units.append({
                    'idx': i,
                    'slave_id': unit['slave_id'],
                    'name': unit['name'],
                    'coil_count': 8
                })
        return render_template('relays.html', relays=relay_units)

    @app.route('/sensors')
    def sensors():
        return render_template('sensors.html')

    @app.route('/calibrate')
    def calibrate():
        return render_template('calibrate.html', units=Config.UNITS)

    @app.route('/aio')
    def aio():
        return render_template('aio.html', fallback_mode=fallback_mode)

    @app.route('/r302')
    def r302():
        return render_template('R302.html')