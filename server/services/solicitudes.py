"""Logica de negocio de las solicitudes (autorizaciones genericas)."""

from models.database import get_db
from services.marcas import listas_para_marca

AUTORIZACIONES_REQUERIDAS = 2

CAMPOS = (
    'fecha', 'empresa', 'marca', 'marca_otro', 'proveedor_tipo', 'proveedor_nombre', 'cuit',
    'tipo_orden', 'duracion_orden', 'concepto', 'concepto_otro', 'monto_total', 'forma_pago',
    'cbu', 'condicion_pago', 'condicion_dias', 'condicion_otras', 'contacto_nombre',
    'contacto_telefono', 'contacto_mail', 'observaciones', 'solicitado_por', 'factura_nombre',
    'factura_archivo', 'factura_numero',
)

# Campos sin los que el formulario no tiene sentido enviar a autorizar.
OBLIGATORIOS = ('fecha', 'empresa', 'marca', 'proveedor_nombre', 'proveedor_tipo', 'tipo_orden',
                'concepto', 'solicitado_por')


def _fila_a_dict(row):
    return {k: row[k] for k in row.keys()}


def validar(datos):
    """Devuelve lista de errores legibles."""
    errores = []
    for campo in OBLIGATORIOS:
        if not str(datos.get(campo) or '').strip():
            errores.append(f'Falta completar: {campo.replace("_", " ")}')
    if float(datos.get('monto_total') or 0) <= 0:
        errores.append('El monto presupuesto final debe ser mayor a cero')
    if datos.get('marca') == 'OTRO' and not str(datos.get('marca_otro') or '').strip():
        errores.append('Indicá cuál es la marca en "Otro"')
    if datos.get('concepto') == 'otros' and not str(datos.get('concepto_otro') or '').strip():
        errores.append('Indicá cuál es el concepto en "Otros"')
    if datos.get('tipo_orden') == 'abierta' and not str(datos.get('duracion_orden') or '').strip():
        errores.append('Indicá la duración de la orden abierta')
    if datos.get('forma_pago') == 'transferencia' and not str(datos.get('cbu') or '').strip():
        errores.append('Para transferencia hace falta el CBU')
    return errores


def crear(datos, items):
    conn = get_db()
    try:
        valores = [datos.get(c, '') if c != 'monto_total' else float(datos.get(c) or 0) for c in CAMPOS]
        cur = conn.execute(
            f'INSERT INTO solicitudes ({", ".join(CAMPOS)}) VALUES ({", ".join("?" * len(CAMPOS))})',
            valores,
        )
        solicitud_id = cur.lastrowid
        _guardar_items(conn, solicitud_id, items)
        conn.commit()
        return solicitud_id
    finally:
        conn.close()


def actualizar(solicitud_id, datos, items):
    conn = get_db()
    try:
        row = conn.execute('SELECT estado FROM solicitudes WHERE id = ?', (solicitud_id,)).fetchone()
        if not row:
            return False, 'La solicitud no existe'
        if row['estado'] == 'autorizada':
            return False, 'La solicitud ya está autorizada y no se puede modificar'
        # Si alguien ya firmó, editar cambiaría lo que firmó: se limpian las firmas.
        conn.execute('DELETE FROM autorizaciones WHERE solicitud_id = ?', (solicitud_id,))
        sets = ', '.join(f'{c} = ?' for c in CAMPOS)
        valores = [datos.get(c, '') if c != 'monto_total' else float(datos.get(c) or 0) for c in CAMPOS]
        conn.execute(
            f'UPDATE solicitudes SET {sets}, updated_at = datetime("now", "localtime") WHERE id = ?',
            valores + [solicitud_id],
        )
        conn.execute('DELETE FROM items WHERE solicitud_id = ?', (solicitud_id,))
        _guardar_items(conn, solicitud_id, items)
        conn.commit()
        return True, ''
    finally:
        conn.close()


def _guardar_items(conn, solicitud_id, items):
    for i, item in enumerate(items or []):
        conn.execute(
            'INSERT INTO items (solicitud_id, descripcion, precio, cantidad, total, orden) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (solicitud_id, item.get('descripcion', ''), float(item.get('precio') or 0),
             float(item.get('cantidad') or 0), float(item.get('total') or 0), i),
        )


def obtener(solicitud_id):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM solicitudes WHERE id = ?', (solicitud_id,)).fetchone()
        if not row:
            return None
        solicitud = _fila_a_dict(row)
        solicitud['items'] = [
            _fila_a_dict(r) for r in
            conn.execute('SELECT * FROM items WHERE solicitud_id = ? ORDER BY orden', (solicitud_id,))
        ]
        solicitud['autorizaciones'] = [
            _fila_a_dict(r) for r in conn.execute(
                'SELECT a.id, a.fecha, a.excedio_tope, a.monto_tope, au.nombre, au.cargo '
                'FROM autorizaciones a JOIN autorizados au ON au.id = a.autorizado_id '
                'WHERE a.solicitud_id = ? ORDER BY a.fecha', (solicitud_id,))
        ]
        solicitud['autorizaciones_requeridas'] = AUTORIZACIONES_REQUERIDAS
        solicitud['autorizaciones_faltantes'] = max(
            0, AUTORIZACIONES_REQUERIDAS - len(solicitud['autorizaciones']))
        return solicitud
    finally:
        conn.close()


def listar(estado=None, busqueda=None):
    conn = get_db()
    try:
        sql = ('SELECT s.*, (SELECT COUNT(*) FROM autorizaciones a WHERE a.solicitud_id = s.id) '
               'AS firmas FROM solicitudes s WHERE 1=1')
        params = []
        if estado:
            sql += ' AND s.estado = ?'
            params.append(estado)
        if busqueda:
            sql += (' AND (s.proveedor_nombre LIKE ? OR s.cuit LIKE ? OR s.marca LIKE ? '
                    'OR s.factura_numero LIKE ? OR s.solicitado_por LIKE ?)')
            params += [f'%{busqueda}%'] * 5
        sql += ' ORDER BY s.id DESC'
        return [_fila_a_dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def eliminar(solicitud_id):
    conn = get_db()
    try:
        cur = conn.execute('DELETE FROM solicitudes WHERE id = ?', (solicitud_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def autorizados_para(solicitud):
    """Autorizados habilitados para la marca de la solicitud, marcando quien excede su tope
    y quien ya firmó."""
    listas = listas_para_marca(solicitud['marca'])
    monto = float(solicitud['monto_total'] or 0)
    ya_firmaron = {a['nombre'] for a in solicitud['autorizaciones']}
    conn = get_db()
    try:
        placeholders = ', '.join('?' * len(listas))
        rows = conn.execute(
            f'SELECT id, nombre, cargo, lista, monto_autorizado, conceptos, '
            f'(pin_hash IS NOT NULL) AS tiene_pin FROM autorizados '
            f'WHERE activo = 1 AND lista IN ({placeholders}) ORDER BY lista, nombre', listas).fetchall()
    finally:
        conn.close()

    autorizados = []
    for r in rows:
        tope = r['monto_autorizado']
        autorizados.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'cargo': r['cargo'],
            'lista': r['lista'],
            'monto_autorizado': tope,
            'sin_limite': tope is None,
            'conceptos': r['conceptos'],
            'tiene_pin': bool(r['tiene_pin']),
            'excede_tope': tope is not None and monto > tope,
            'ya_firmo': r['nombre'] in ya_firmaron,
        })
    return autorizados
