import os
import sqlite3

from models.autorizados_seed import AUTORIZADOS

DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'app.db'))

SCHEMA = """
CREATE TABLE IF NOT EXISTS autorizados (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL UNIQUE,
    cargo             TEXT NOT NULL,
    lista             TEXT NOT NULL,           -- nissan | jeep | kia | multimarca
    monto_autorizado  REAL,                    -- NULL = SIN LIMITE
    conceptos         TEXT NOT NULL DEFAULT '',
    pin_hash          TEXT,                    -- NULL = todavia no dio de alta su PIN
    activo            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS solicitudes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha               TEXT NOT NULL,
    empresa             TEXT NOT NULL DEFAULT '',
    marca               TEXT NOT NULL DEFAULT '',
    marca_otro          TEXT NOT NULL DEFAULT '',
    proveedor_tipo      TEXT NOT NULL DEFAULT '',   -- nuevo | habitual
    proveedor_nombre    TEXT NOT NULL DEFAULT '',
    cuit                TEXT NOT NULL DEFAULT '',
    tipo_orden          TEXT NOT NULL DEFAULT '',   -- cerrada | abierta
    duracion_orden      TEXT NOT NULL DEFAULT '',
    concepto            TEXT NOT NULL DEFAULT '',   -- publicidad | muebles | gastos | reparacion | comisiones | otros
    concepto_otro       TEXT NOT NULL DEFAULT '',
    monto_total         REAL NOT NULL DEFAULT 0,
    forma_pago          TEXT NOT NULL DEFAULT '',   -- efectivo | cheque | echeq | transferencia
    cbu                 TEXT NOT NULL DEFAULT '',
    condicion_pago      TEXT NOT NULL DEFAULT '',   -- contado | cuenta_corriente | otras
    condicion_dias      TEXT NOT NULL DEFAULT '',   -- 7 | 20 | 30 | <otro numero>
    condicion_otras     TEXT NOT NULL DEFAULT '',
    contacto_nombre     TEXT NOT NULL DEFAULT '',
    contacto_telefono   TEXT NOT NULL DEFAULT '',
    contacto_mail       TEXT NOT NULL DEFAULT '',
    observaciones       TEXT NOT NULL DEFAULT '',
    solicitado_por      TEXT NOT NULL DEFAULT '',
    estado              TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente | autorizada
    factura_nombre      TEXT NOT NULL DEFAULT '',
    factura_archivo     TEXT NOT NULL DEFAULT '',
    factura_numero      TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id  INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    descripcion   TEXT NOT NULL DEFAULT '',
    precio        REAL NOT NULL DEFAULT 0,
    cantidad      REAL NOT NULL DEFAULT 0,
    total         REAL NOT NULL DEFAULT 0,
    orden         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS autorizaciones (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id   INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    autorizado_id  INTEGER NOT NULL REFERENCES autorizados(id),
    excedio_tope   INTEGER NOT NULL DEFAULT 0,
    monto_tope     REAL,
    fecha          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (solicitud_id, autorizado_id)
);

CREATE INDEX IF NOT EXISTS idx_items_solicitud ON items(solicitud_id);
CREATE INDEX IF NOT EXISTS idx_auth_solicitud ON autorizaciones(solicitud_id);
"""


def get_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        _seed_autorizados(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_autorizados(conn):
    """Inserta los autorizados que falten y actualiza cargo/monto/conceptos de los
    existentes, sin tocar el PIN ya dado de alta."""
    for a in AUTORIZADOS:
        row = conn.execute('SELECT id FROM autorizados WHERE nombre = ?', (a['nombre'],)).fetchone()
        if row:
            conn.execute(
                'UPDATE autorizados SET cargo = ?, lista = ?, monto_autorizado = ?, conceptos = ? WHERE id = ?',
                (a['cargo'], a['lista'], a['monto_autorizado'], a['conceptos'], row['id']),
            )
        else:
            conn.execute(
                'INSERT INTO autorizados (nombre, cargo, lista, monto_autorizado, conceptos) VALUES (?, ?, ?, ?, ?)',
                (a['nombre'], a['cargo'], a['lista'], a['monto_autorizado'], a['conceptos']),
            )
