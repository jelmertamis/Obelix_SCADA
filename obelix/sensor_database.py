import sqlite3
from datetime import datetime
from obelix.config import Config

def init_sensor_db():
    """
    Initialiseer de losse sensor-database met tabel sensor_data.
    """
    conn = sqlite3.connect(Config.SENSOR_DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            timestamp   TEXT    NOT NULL,
            unit_index  INTEGER NOT NULL,
            channel     INTEGER NOT NULL,
            raw         REAL,
            value       REAL    NOT NULL,
            unit        TEXT,
            PRIMARY KEY(timestamp, unit_index, channel)
        )
    ''')
    conn.commit()
    conn.close()

def save_sensor_reading(unit_index, channel, raw, value, unit_str=''):
    """
    Sla een sensorlezing op (raw mag None zijn).
    """
    conn = sqlite3.connect(Config.SENSOR_DB_FILE)
    c = conn.cursor()
    ts = datetime.utcnow().isoformat()
    c.execute('''
        INSERT OR REPLACE INTO sensor_data
            (timestamp, unit_index, channel, raw, value, unit)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (ts, unit_index, channel, raw, value, unit_str))
    conn.commit()
    conn.close()

def get_sensor_readings(unit_index, channel, start=None, end=None):
    """
    Haal sensorlezingen op met filters:
      - unit_index: verplicht int
      - channel:     verplicht int
      - start:       optionele ISO timestamp string
      - end:         optionele ISO timestamp string
    Retourneert lijst dicts gesorteerd op timestamp ASC.
    """
    conn = sqlite3.connect(Config.SENSOR_DB_FILE)
    c = conn.cursor()

    query = 'SELECT timestamp, unit_index, channel, raw, value, unit FROM sensor_data'
    clauses = []
    params = []

    clauses.append('unit_index = ?'); params.append(unit_index)
    clauses.append('channel    = ?'); params.append(channel)
    if start:
        clauses.append('timestamp >= ?'); params.append(start)
    if end:
        clauses.append('timestamp <= ?'); params.append(end)

    query += ' WHERE ' + ' AND '.join(clauses)
    query += ' ORDER BY timestamp ASC'

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    return [
        {
            'timestamp': ts,
            'unit_index': ui,
            'channel': ch,
            'raw': raw,
            'value': val,
            'unit': u
        }
        for ts, ui, ch, raw, val, u in rows
    ]
