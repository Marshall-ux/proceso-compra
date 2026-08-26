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
    activo            INTEGER NOT NULL DEFAULT 1,
    -- Alta de PIN: el admin genera un codigo de un solo uso y se lo entrega a la
    -- persona; sin ese codigo nadie puede darle de alta el PIN a otro.
    codigo_alta_hash  TEXT,
    codigo_alta_fecha TEXT,
    -- Bloqueo por intentos fallidos.
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta   TEXT
);

-- Auditoria de intentos: quien intento firmar, cuando y con que resultado.
CREATE TABLE IF NOT EXISTS intentos_pin (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    autorizado_id INTEGER NOT NULL REFERENCES autorizados(id) ON DELETE CASCADE,
    solicitud_id  INTEGER,
    resultado     TEXT NOT NULL,   -- ok | pin_incorrecto | bloqueado | sin_pin | alta | codigo_invalido
    fecha         TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
    -- Legacy: factura unica. Se mantiene por compatibilidad; las facturas nuevas
    -- viven en la tabla 'facturas' (una solicitud puede tener varias).
    factura_nombre      TEXT NOT NULL DEFAULT '',
    factura_archivo     TEXT NOT NULL DEFAULT '',
    factura_numero      TEXT NOT NULL DEFAULT '',
    -- V2
    criticidad          TEXT NOT NULL DEFAULT '',   -- urgente | informado | otro
    criticidad_obs      TEXT NOT NULL DEFAULT '',    -- detalle cuando criticidad = otro
    requiere_oc         TEXT NOT NULL DEFAULT '',    -- si | no
    autopack_ok         INTEGER NOT NULL DEFAULT 0,  -- cargado en Autopack (bloquea el Excel)
    cbu_imagen          TEXT NOT NULL DEFAULT '',    -- archivo JPG del CBU
    legajo_nombre       TEXT NOT NULL DEFAULT '',
    legajo_archivo      TEXT NOT NULL DEFAULT '',    -- PDF del legajo impositivo
    empresas            TEXT NOT NULL DEFAULT '',    -- JSON: multi-selección de empresas
    marcas              TEXT NOT NULL DEFAULT '',    -- JSON: multi-selección de marcas
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS facturas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id  INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    nombre        TEXT NOT NULL DEFAULT '',   -- nombre original del archivo
    archivo       TEXT NOT NULL DEFAULT '',   -- nombre guardado en uploads/
    numero        TEXT NOT NULL DEFAULT '',   -- nro de comprobante leido del PDF
    orden         INTEGER NOT NULL DEFAULT 0,
    pago_id       INTEGER REFERENCES pagos(id) ON DELETE CASCADE  -- NULL = factura de la AGC
);

-- Pagos imputados a una AGC ya autorizada (anticipos/avances de una obra, viajes de
-- un flete, etc.). La AGC controla el presupuesto; cada pago se firma como conformidad
-- de que el servicio/avance se dio. No re-autorizan la AGC.
CREATE TABLE IF NOT EXISTS pagos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id  INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    descripcion   TEXT NOT NULL DEFAULT '',
    monto         REAL NOT NULL DEFAULT 0,
    fecha         TEXT NOT NULL DEFAULT '',    -- fecha del pago/factura (dd/mm/aaaa)
    cargado_por   TEXT NOT NULL DEFAULT '',
    estado        TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente | conforme
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Firmas de conformidad de cada pago (misma regla que la AGC: 1 firma dentro del tope,
-- 2 si lo supera).
CREATE TABLE IF NOT EXISTS pago_firmas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pago_id       INTEGER NOT NULL REFERENCES pagos(id) ON DELETE CASCADE,
    autorizado_id INTEGER NOT NULL REFERENCES autorizados(id),
    excedio_tope  INTEGER NOT NULL DEFAULT 0,
    monto_tope    REAL,
    fecha         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (pago_id, autorizado_id)
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

-- Acta de eliminación: al borrar una solicitud se guarda acá una copia de sus
-- datos clave + el motivo, para tener trazabilidad de qué se borró y por qué.
CREATE TABLE IF NOT EXISTS eliminaciones (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id      INTEGER,                 -- id original (la fila ya no existe)
    proveedor_nombre  TEXT NOT NULL DEFAULT '',
    cuit              TEXT NOT NULL DEFAULT '',
    marca             TEXT NOT NULL DEFAULT '',
    empresa           TEXT NOT NULL DEFAULT '',
    monto_total       REAL NOT NULL DEFAULT 0,
    estado            TEXT NOT NULL DEFAULT '',   -- estado que tenía al borrarse
    fecha_factura     TEXT NOT NULL DEFAULT '',
    factura_numero    TEXT NOT NULL DEFAULT '',
    solicitado_por    TEXT NOT NULL DEFAULT '',
    firmas            INTEGER NOT NULL DEFAULT 0,
    motivo            TEXT NOT NULL,
    eliminado_por     TEXT NOT NULL DEFAULT '',
    fecha             TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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


# Columnas agregadas en V2: para bases que ya existen se suman con ALTER TABLE.
_COLUMNAS_V2 = {
    'criticidad': "TEXT NOT NULL DEFAULT ''",
    'criticidad_obs': "TEXT NOT NULL DEFAULT ''",
    'requiere_oc': "TEXT NOT NULL DEFAULT ''",
    'autopack_ok': 'INTEGER NOT NULL DEFAULT 0',
    'cbu_imagen': "TEXT NOT NULL DEFAULT ''",
    'legajo_nombre': "TEXT NOT NULL DEFAULT ''",
    'legajo_archivo': "TEXT NOT NULL DEFAULT ''",
    # Multi-selección de empresa y marca (JSON). Los campos escalares empresa/marca
    # se mantienen con el primer valor, para compatibilidad y para búsqueda/listado.
    'empresas': "TEXT NOT NULL DEFAULT ''",
    'marcas': "TEXT NOT NULL DEFAULT ''",
}


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        _migrar(conn)
        _seed_autorizados(conn)
        conn.commit()
    finally:
        conn.close()


_COLUMNAS_AUTORIZADOS = {
    'codigo_alta_hash': 'TEXT',
    'codigo_alta_fecha': 'TEXT',
    'intentos_fallidos': 'INTEGER NOT NULL DEFAULT 0',
    'bloqueado_hasta': 'TEXT',
}

_COLUMNAS_FACTURAS = {
    'pago_id': 'INTEGER',   # NULL = factura de la AGC; con valor = factura de un pago
}


def _migrar(conn):
    """Agrega a una base preexistente las columnas nuevas que falten."""
    for tabla, columnas in (('solicitudes', _COLUMNAS_V2), ('autorizados', _COLUMNAS_AUTORIZADOS),
                            ('facturas', _COLUMNAS_FACTURAS)):
        existentes = {r['name'] for r in conn.execute(f'PRAGMA table_info({tabla})')}
        for columna, definicion in columnas.items():
            if columna not in existentes:
                conn.execute(f'ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}')


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

    # El roster (esta lista) es la fuente de verdad de quién es autorizante. A quien ya
    # no figura acá (bajas), se lo deja inactivo; no se borra, para conservar su historial.
    # El activo/inactivo de quienes SÍ están en el roster lo maneja el panel de admin.
    nombres = [a['nombre'] for a in AUTORIZADOS]
    marcadores = ', '.join('?' * len(nombres))
    conn.execute(
        f'UPDATE autorizados SET activo = 0 WHERE nombre NOT IN ({marcadores})', nombres)
