# app.py
import time
import threading
import logging
import sqlite3

import minimalmodbus
import serial
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

# ─── Configuration ──────────────────────────────────────────────────────────
RS485_PORT = '/dev/ttyUSB0'
BAUDRATE   = 9600
PARITY     = serial.PARITY_EVEN
STOPBITS   = 1
BYTESIZE   = 8
TIMEOUT    = 1

DB_FILE = 'settings.db'

UNITS = [
    {'slave_id': 1,  'name': 'Relay Module 1', 'type': 'relay'},
    {'slave_id': 2,  'name': 'Relay Module 2', 'type': 'relay'},
    {'slave_id': 3,  'name': 'Relay Module 3', 'type': 'relay'},
    {'slave_id': 4,  'name': 'Relay Module 4', 'type': 'relay'},
    {'slave_id': 5,  'name': 'Analog Input 1','type': 'analog'},
    {'slave_id': 6,  'name': 'Analog Input 2','type': 'analog'},
    {'slave_id': 7,  'name': 'Analog Input 3','type': 'analog'},
    {'slave_id': 8,  'name': 'Analog Input 4','type': 'analog'},
    {'slave_id': 9,  'name': 'EX1608DD',      'type': 'relay'},
    {'slave_id': 10, 'name': 'EX04AIO',        'type': 'aio'},
]
AIO_IDX = next(i for i,u in enumerate(UNITS) if u['type']=='aio')

# ─── Globals ────────────────────────────────────────────────────────────────
clients       = []
fallback_mode = False
log_messages  = []
MAX_LOG       = 20

# ─── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
def log(msg):
    ts = time.strftime('%H:%M:%S')
    entry = f'[{ts}] {msg}'
    log_messages.append(entry)
    if len(log_messages) > MAX_LOG:
        del log_messages[:-MAX_LOG]
    print(entry)

# ─── Database helpers ───────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS calibration (
        unit_index INTEGER NOT NULL,
        channel     INTEGER NOT NULL,
        scale       REAL    NOT NULL,
        offset      REAL    NOT NULL,
        phys_min    REAL    NOT NULL,
        phys_max    REAL    NOT NULL,
        PRIMARY KEY(unit_index, channel)
      )
    ''')
    c.execute('''
      CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''')
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      INSERT INTO settings(key, value)
      VALUES (?, ?)
      ON CONFLICT(key) DO UPDATE SET value=excluded.value
    ''', (key, str(value)))
    conn.commit()
    conn.close()

def get_calibration(unit_index, channel):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
      SELECT scale, offset
      FROM calibration
      WHERE unit_index=? AND channel=?
    ''', (unit_index, channel))
    row = c.fetchone()
    conn.close()
    if row:
        return {'scale': row[0], 'offset': row[1]}
    return {'scale': 1.0, 'offset': 0.0}

def save_calibration(unit_index, channel, scale, offset, phys_min, phys_max):
    conn = sqlite3.connect(DB_FILE)
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

# ─── Dummy fallback for Modbus unavailable ──────────────────────────────────
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

# ─── Modbus initialization with auto-Dummy on failure ──────────────────────
def init_modbus():
    global fallback_mode, clients
    clients = []
    try:
        for u in UNITS:
            inst = minimalmodbus.Instrument(RS485_PORT, u['slave_id'], mode=minimalmodbus.MODE_RTU)
            inst.serial.baudrate   = BAUDRATE
            inst.serial.parity     = minimalmodbus.serial.PARITY_EVEN
            inst.serial.stopbits   = STOPBITS
            inst.serial.bytesize   = BYTESIZE
            inst.serial.timeout    = TIMEOUT
            inst.clear_buffers_before_each_transaction = True

            # quick test-read
            if u['type']=='relay':
                inst.read_bit(0, functioncode=1)
            else:
                inst.read_register(0, functioncode=4)

            clients.append(inst)
            log(f"Modbus OK voor {u['name']} (ID {u['slave_id']})")
        fallback_mode = False
    except Exception as e:
        log(f"Modbus niet gevonden ({e}), overschakelen naar Dummy-modus.")
        clients = [DummyModbusClient() for _ in UNITS]
        fallback_mode = True

# ─── Sensor background monitor ──────────────────────────────────────────────
def sensor_monitor():
    while True:
        data = []
        for i,u in enumerate(UNITS):
            if u['type']=='analog':
                inst = clients[i]
                for ch in range(4):
                    try:
                        raw = inst.read_register(ch, functioncode=4)
                        cal = get_calibration(i, ch)
                        val = raw * cal['scale'] + cal['offset']
                        data.append({
                            'name':     u['name'],
                            'slave_id': u['slave_id'],
                            'channel':  ch,
                            'raw':      raw,
                            'value':    round(val
