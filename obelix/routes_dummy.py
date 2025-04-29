# obelix/routes_dummy.py

from flask import Blueprint, render_template, request, jsonify
from obelix.config import Config
from obelix.database import get_dummy_value, set_dummy_value

dummy_bp = Blueprint('dummy', __name__)

@dummy_bp.route('/dummy')
def dummy_page():
    """
    HTML-pagina waarop je voor elk analoog kanaal een dummy-waarde kunt instellen.
    """
    analog_units = [
        {'idx': i, 'name': u['name'], 'slave_id': u['slave_id']}
        for i, u in enumerate(Config.UNITS)
        if u['type'] == 'analog'
    ]
    return render_template('dummy.html', units=analog_units)

@dummy_bp.route('/api/dummy_values', methods=['GET'])
def api_get_dummy_values():
    """
    Retourneer alle huidige dummy-sensorwaarden als JSON-lijst:
      [{ 'unit_index': i, 'channel': ch, 'value': val_or_null }, …]
    """
    payload = []
    for i, u in enumerate(Config.UNITS):
        if u['type'] == 'analog':
            for ch in range(4):
                val = get_dummy_value(i, ch)
                payload.append({
                    'unit_index': i,
                    'channel': ch,
                    'value': val  # None als nog niet ingesteld
                })
    return jsonify(payload)

@dummy_bp.route('/api/dummy_value', methods=['POST'])
def api_set_dummy_value():
    """
    Stel één dummy-waarde in. Verwacht JSON:
      { 'unit_index': int, 'channel': int, 'value': float }
    """
    data = request.get_json() or {}
    try:
        unit_index = int(data['unit_index'])
        channel    = int(data['channel'])
        value      = float(data['value'])
    except (KeyError, TypeError, ValueError):
        return jsonify({'error': 'Invalid payload'}), 400

    set_dummy_value(unit_index, channel, value)
    return jsonify({'status': 'ok'})
