import sqlite3
from obelix.config import Config

def init_db():
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    # Bestaand calibration‐schema
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
    # Controleer of kolom 'unit' al bestaat, zo niet: toevoegen
    cols = [row[1] for row in c.execute("PRAGMA table_info(calibration)").fetchall()]
    if 'unit' not in cols:
        c.execute('ALTER TABLE calibration ADD COLUMN unit TEXT DEFAULT ""')

    # Overige tabellen
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

    # **Nieuw: tabel voor handmatige dummy-sensorwaarden**
    c.execute('''
        CREATE TABLE IF NOT EXISTS dummy_sensor (
            unit_index INTEGER NOT NULL,
            channel INTEGER NOT NULL,
            value REAL NOT NULL,
            PRIMARY KEY(unit_index, channel)
        )
    ''')

    # Initiele relay_states vullen
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
        SELECT scale, offset, phys_min, phys_max, unit
        FROM calibration
        WHERE unit_index=? AND channel=?
    ''', (unit_index, channel))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'scale':    row[0],
            'offset':   row[1],
            'phys_min': row[2],
            'phys_max': row[3],
            'unit':     row[4] or ''
        }
    # Standaardwaarden als nog niet gekalibreerd
    return {'scale': 1.0, 'offset': 0.0, 'phys_min': 0.0, 'phys_max': 0.0, 'unit': ''}

def save_calibration(unit_index, channel, scale, offset, phys_min, phys_max, unit):
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO calibration(unit_index, channel, scale, offset, phys_min, phys_max, unit)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(unit_index, channel) DO UPDATE SET
            scale=excluded.scale,
            offset=excluded.offset,
            phys_min=excluded.phys_min,
            phys_max=excluded.phys_max,
            unit=excluded.unit
    ''', (unit_index, channel, scale, offset, phys_min, phys_max, unit))
    conn.commit()
    conn.close()

def get_all_calibrations():
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT unit_index, channel, scale, offset, phys_min, phys_max, unit
        FROM calibration
    ''')
    payload = {}
    for u, ch, sc, off, pmin, pmax, unit in c.fetchall():
        payload[f"{u}-{ch}"] = {
            'scale':    sc,
            'offset':   off,
            'phys_min': pmin,
            'phys_max': pmax,
            'unit':     unit or ''
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
    ''', (unit_index, coil_index))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ---------------------------------------------------------------------
# **Nieuwe helper-functies voor dummy-sensorwaarden**
# ---------------------------------------------------------------------

def set_dummy_value(unit_index, channel, value):
    """
    Sla een handmatig ingestelde dummy-waarde op voor een sensorkanaal.
    """
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO dummy_sensor(unit_index, channel, value)
        VALUES(?, ?, ?)
        ON CONFLICT(unit_index, channel) DO UPDATE SET value=excluded.value
    ''', (unit_index, channel, float(value)))
    conn.commit()
    conn.close()

def get_dummy_value(unit_index, channel):
    """
    Haal de handmatig ingestelde dummy-waarde op, of None als niet gedefinieerd.
    """
    conn = sqlite3.connect(Config.DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT value FROM dummy_sensor
        WHERE unit_index=? AND channel=?
    ''', (unit_index, channel))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None
