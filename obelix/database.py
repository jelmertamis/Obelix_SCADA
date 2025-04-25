import sqlite3
from obelix.config import Config

def init_db():
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS calibration (
            unit_index INTEGER NOT NULL,
            channel INTEGER NOT NULL,
            scale REAL NOT NULL,
            offset REAL NOT NULL,
            phys_min REAL NOT NULL,
            phys_max REAL NOT NULL,
            PRIMARY KEY(unit_index, channel)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS aio_settings (
            channel INTEGER PRIMARY KEY,
            percent REAL NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS relay_states (
            unit_index INTEGER NOT NULL,
            coil_index INTEGER NOT NULL,
            state TEXT NOT NULL,
            PRIMARY KEY(unit_index, coil_index)
        )
    ''')
    # Voeg initiële relaisstatussen toe
    for i, unit in enumerate(Config.UNITS):
        if unit['type'] == 'relay':
            for coil in range(8):
                c.execute('''
                    INSERT OR IGNORE INTO relay_states(unit_index, coil_index, state)
                    VALUES (?, ?, ?)
                ''', (i, coil, 'OFF'))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO settings(key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    ''', (key, str(value)))
    conn.commit()
    conn.close()

def get_calibration(unit_index, channel):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT scale, offset FROM calibration
        WHERE unit_index=? AND channel=?
    ''', (unit_index, channel))
    row = c.fetchone()
    conn.close()
    if row:
        return {'scale': row[0], 'offset': row[1]}
    return {'scale': 1.0, 'offset': 0.0}

def save_calibration(unit_index, channel, scale, offset, phys_min, phys_max):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO calibration(unit_index,channel,scale,offset,phys_min,phys_max)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(unit_index,channel) DO UPDATE SET
            scale=excluded.scale, offset=excluded.offset,
            phys_min=excluded.phys_min, phys_max=excluded.phys_max
    ''', (unit_index, channel, scale, offset, phys_min, phys_max))
    conn.commit()
    conn.close()

def get_all_calibrations():
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('SELECT unit_index, channel, scale, offset, phys_min, phys_max FROM calibration')
    payload = {}
    for u, ch, sc, off, pmin, pmax in c.fetchall():
        payload[f"{u}-{ch}"] = {
            'scale': sc,
            'offset': off,
            'phys_min': pmin,
            'phys_max': pmax
        }
    conn.close()
    return payload

def save_aio_setting(channel, percent):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO aio_settings(channel, percent) VALUES (?, ?)
        ON CONFLICT(channel) DO UPDATE SET percent=excluded.percent
    ''', (channel, percent))
    conn.commit()
    conn.close()

def get_aio_setting(channel):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('SELECT percent FROM aio_settings WHERE channel=?', (channel,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def save_relay_state(unit_index, coil_index, state):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO relay_states(unit_index, coil_index, state) VALUES (?, ?, ?)
        ON CONFLICT(unit_index, coil_index) DO UPDATE SET state=excluded.state
    ''', (unit_index, coil_index, state))
    conn.commit()
    conn.close()

def get_relay_state(unit_index, coil_index):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT state FROM relay_states WHERE unit_index=? AND coil_index=?
    ''', (unit_index, coil_index))  # Gewijzigd: channel → coil_index
    row = c.fetchone()
    conn.close()
    return row[0] if row else None