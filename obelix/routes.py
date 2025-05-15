# obelix/routes.py
from flask import (
    render_template, request, send_file,
    Blueprint, url_for
)
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

plot_bp = Blueprint('plot', __name__)

@plot_bp.route('/plot/sensor')
def sensor_plot_png():
    """
    PNG-endpoint:
      Verplich: unit_index, channel
      Optioneel: start, end (ISO), last_hours (int)
    """
    unit       = request.args.get('unit_index', type=int)
    channel    = request.args.get('channel',    type=int)
    last_hours = request.args.get('last_hours', type=int)
    start      = request.args.get('start')
    end        = request.args.get('end')

    if last_hours:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        end = now.isoformat()
        start = (now - timedelta(hours=last_hours)).isoformat()

    fig = plot_sensor_history(
        unit_index=unit,
        channel=channel,
        start=start,
        end=end
    )
    buf = BytesIO()
    fig.savefig(buf, bbox_inches='tight')
    buf.seek(0)
    return send_file(buf, mimetype='image/png',
                     download_name='sensor_plot.png')

def init_routes(app):
    @app.route('/')
    def index():
        return render_template('dashboard.html', fallback_mode=fallback_mode)

    @app.route('/relays')
    def relays():
        relay_units = []
        for i, u in enumerate(Config.UNITS):
            if u['type']=='relay':
                relay_units.append({
                    'idx': i,
                    'slave_id': u['slave_id'],
                    'name': u['name'],
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
        analog_units = [
            {'idx': i, 'name': u['name'], 'slave_id': u['slave_id']}
            for i,u in enumerate(Config.UNITS) if u['type']=='analog'
        ]
        return render_template(
            'sensor_plot.html',
            units=analog_units,
            plot_url=url_for('plot.sensor_plot_png')
        )
    
    @app.route('/grafana_embed')
    def grafana_embed():
        return render_template('grafana_embed.html')

    @app.route('/sbr')
    def sbr():
        cycle_active = get_setting('sbr_cycle_active', '0') == '1'
        cycle_time_minutes = float(get_setting('sbr_cycle_time_minutes', '1.66667'))
        return render_template('sbr.html', 
                             cycle_active=cycle_active,
                             cycle_time_minutes=cycle_time_minutes)
    
    app.register_blueprint(plot_bp)