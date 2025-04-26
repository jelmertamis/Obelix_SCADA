# obelix/sensor_database.py
import sqlite3
from datetime import datetime
from obelix.config import Config

def init_sensor_db():
    """
    Initialiseer de losstaande sensor-database met tabel voor historische sensorlezingen.
    """
    conn = sqlite3.connect(Config.SENSOR_DB_FILE)
    c = conn.cursor()
    # Maak sensor_data aan met raw optioneel (nullable)
    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            timestamp TEXT NOT NULL,
            unit_index INTEGER NOT NULL,
            channel INTEGER NOT NULL,
            raw REAL,
            value REAL NOT NULL,
            unit TEXT,
            PRIMARY KEY(timestamp, unit_index, channel)
        )
    ''')
    conn.commit()
    conn.close()


def save_sensor_reading(unit_index, channel, raw, value, unit_str=''):
    """
    Sla een sensorlezing op in de losstaande sensor-database.
    raw mag None zijn en wordt dan als NULL opgeslagen.
    """
    conn = sqlite3.connect(Config.SENSOR_DB_FILE)
    c = conn.cursor()
    ts = datetime.utcnow().isoformat()
    c.execute('''
        INSERT OR REPLACE INTO sensor_data(timestamp, unit_index, channel, raw, value, unit)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (ts, unit_index, channel, raw, value, unit_str))
    conn.commit()
    conn.close()


def get_recent_sensor_readings(limit=100):
    """
    Haal de meest recente `limit` sensorlezingen op.
    """
    conn = sqlite3.connect(Config.SENSOR_DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, unit_index, channel, raw, value, unit
        FROM sensor_data
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
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
