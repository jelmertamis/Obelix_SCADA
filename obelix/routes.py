# obelix/routes.py
from flask import render_template, request, send_file, Blueprint, url_for
from io import BytesIO
from obelix.config import Config
from obelix.modbus_client import fallback_mode
from obelix.database import (
    get_setting, set_setting, get_all_calibrations,
    get_relay_state, save_relay_state,
    get_calibration, save_calibration,
    get_aio_setting, save_aio_setting
)
from obelix.sensor_plot import plot_sensor_history

# Blueprint voor plot PNG-endpoints
plot_bp = Blueprint('plot', __name__)

@plot_bp.route('/plot/sensor')
def sensor_plot_png():
    """
    Genereert en retourneert een PNG-plot voor historische sensordata.
    Query-params:
      - unit_index (int, optioneel)
      - channel    (int, optioneel)
      - limit      (int, optioneel, default=100)
    """
    unit = request.args.get('unit_index', type=int)
    ch = request.args.get('channel', type=int)
    limit = request.args.get('limit', default=100, type=int)
    # Genereer Matplotlib-figuur
    fig = plot_sensor_history(unit_index=unit, channel=ch, limit=limit)
    # Schrijf naar buffer
    buf = BytesIO()
    fig.savefig(buf, bbox_inches='tight')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name='sensor_plot.png')


def init_routes(app):
    """
    Registreer alle HTTP-routes op de Flask-app.
    Inclusief dashboard, relays, sensors, calibrate, aio, r302, en sensor_history pagina.
    """
    @app.route('/')
    def index():
        # Dashboard met navigatie
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

    @app.route('/sensor_history')
    def sensor_history():
        # Bouw data voor dropdowns in template
        analog_units = [
            {
                'idx': i,
                'name': u['name'],
                'slave_id': u['slave_id']
            }
            for i, u in enumerate(Config.UNITS) if u['type'] == 'analog'
        ]
        return render_template(
            'sensor_plot.html',
            units=analog_units,
            plot_url=url_for('plot.sensor_plot_png')
        )

    # Registreer blueprint voor PNG endpoints
    app.register_blueprint(plot_bp)
