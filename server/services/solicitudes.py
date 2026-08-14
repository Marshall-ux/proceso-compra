"""Logica de negocio de las solicitudes (autorizaciones genericas)."""

import json

from models.database import get_db
from services.marcas import listas_habilitadas
from services.pins import esta_bloqueado

AUTORIZACIONES_REQUERIDAS = 2

CAMPOS = (
    'fecha', 'empresa', 'marca', 'marca_otro', 'proveedor_tipo', 'proveedor_nombre', 'cuit',
    'tipo_orden', 'duracion_orden', 'concepto', 'concepto_otro', 'monto_total', 'forma_pago',
    'cbu', 'condicion_pago', 'condicion_dias', 'condicion_otras', 'contacto_nombre',
    'contacto_telefono', 'contacto_mail', 'observaciones', 'solicitado_por', 'factura_nombre',
    'factura_archivo', 'factura_numero',
    # V2
    'criticidad', 'criticidad_obs', 'requiere_oc', 'autopack_ok', 'cbu_imagen',
    'legajo_nombre', 'legajo_archivo',
    # Multi-selección (JSON)
    'empresas', 'marcas',
)

# Columnas numericas: se guardan como numero, no como texto.
CAMPOS_FLOAT = {'monto_total'}
CAMPOS_INT = {'autopack_ok'}

CRITICIDADES = ('urgente', 'informado', 'otro')

# Campos sin los que el formulario no tiene sentido enviar a autorizar.
OBLIGATORIOS = ('fecha', 'proveedor_nombre', 'proveedor_tipo', 'tipo_orden',
                'concepto', 'solicitado_por', 'criticidad')


def _fila_a_dict(row):
    return {k: row[k] for k in row.keys()}


def lista_multi(datos, campo_lista, campo_scalar):
    """Extrae una lista de valores limpia de la multi-selección (empresas/marcas),
    aceptando tanto la lista nueva como el campo escalar viejo. Sin duplicados."""
    val = datos.get(campo_lista)
    if isinstance(val, str) and val.strip().startswith('['):
        try:
            val = json.loads(val)
        except ValueError:
            val = None
    if isinstance(val, list):
        crudos = [str(x).strip() for x in val]
    else:
        escalar = str(datos.get(campo_scalar) or '').strip()
        crudos = [escalar] if escalar else []
    vistos, salida = set(), []
    for x in crudos:
        if x and x not in vistos:
            vistos.add(x)
            salida.append(x)
    return salida


def _normalizar(datos):
    """Devuelve una copia de datos con empresas/marcas como JSON y los escalares
    empresa/marca fijados al primer valor (para búsqueda, listado y compatibilidad)."""
    empresas = lista_multi(datos, 'empresas', 'empresa')
    marcas = lista_multi(datos, 'marcas', 'marca')
    return {
        **datos,
        'empresas': json.dumps(empresas, ensure_ascii=False),
        'marcas': json.dumps(marcas, ensure_ascii=False),
        'empresa': empresas[0] if empresas else '',
        'marca': marcas[0] if marcas else '',
    }


def _valor(campo, datos):
    """Coerciona el valor de un campo al tipo de su columna."""
    bruto = datos.get(campo)
    if campo in CAMPOS_FLOAT:
        try:
            return float(bruto or 0)
        except (TypeError, ValueError):
            return 0.0
    if campo in CAMPOS_INT:
        return 1 if str(bruto) in ('1', 'true', 'True') or bruto is True else 0
    return bruto if bruto is not None else ''


def validar(datos):
    """Devuelve lista de errores legibles."""
    errores = []
    for campo in OBLIGATORIOS:
        if not str(datos.get(campo) or '').strip():
            errores.append(f'Falta completar: {campo.replace("_", " ")}')
    empresas = lista_multi(datos, 'empresas', 'empresa')
    marcas = lista_multi(datos, 'marcas', 'marca')
    if not empresas:
        errores.append('Seleccioná al menos una empresa a la que imputar el pago')
    if not marcas:
        errores.append('Seleccioná al menos una marca')
    if float(datos.get('monto_total') or 0) <= 0:
        errores.append('El monto presupuesto final debe ser mayor a cero')
    if 'OTRO' in marcas and not str(datos.get('marca_otro') or '').strip():
        errores.append('Indicá cuál es la marca en "Otro"')
    if datos.get('concepto') == 'otros' and not str(datos.get('concepto_otro') or '').strip():
        errores.append('Indicá cuál es el concepto en "Otros"')
    if datos.get('tipo_orden') == 'abierta' and not str(datos.get('duracion_orden') or '').strip():
        errores.append('Indicá la duración de la orden abierta')
    if (datos.get('forma_pago') == 'transferencia'
            and not str(datos.get('cbu') or '').strip()
            and not str(datos.get('cbu_imagen') or '').strip()):
        errores.append('Para transferencia hace falta el CBU (número o imagen)')
    if datos.get('criticidad') and datos.get('criticidad') not in CRITICIDADES:
        errores.append('Criticidad inválida')
    if datos.get('criticidad') == 'otro' and not str(datos.get('criticidad_obs') or '').strip():
        errores.append('Indicá el detalle de la criticidad en "Otro"')
    return errores


def crear(datos, items, facturas=None):
    datos = _normalizar(datos)
    conn = get_db()
    try:
        valores = [_valor(c, datos) for c in CAMPOS]
        cur = conn.execute(
            f'INSERT INTO solicitudes ({", ".join(CAMPOS)}) VALUES ({", ".join("?" * len(CAMPOS))})',
            valores,
        )
        solicitud_id = cur.lastrowid
        _guardar_items(conn, solicitud_id, items)
        _guardar_facturas(conn, solicitud_id, facturas)
        conn.commit()
        return solicitud_id
    finally:
        conn.close()


def actualizar(solicitud_id, datos, items, facturas=None):
    conn = get_db()
    try:
        row = conn.execute('SELECT estado FROM solicitudes WHERE id = ?', (solicitud_id,)).fetchone()
        if not row:
            return False, 'La solicitud no existe'
        if row['estado'] == 'autorizada':
            return False, 'La solicitud ya está autorizada y no se puede modificar'
        datos = _normalizar(datos)
        # Si alguien ya firmó, editar cambiaría lo que firmó: se limpian las firmas.
        conn.execute('DELETE FROM autorizaciones WHERE solicitud_id = ?', (solicitud_id,))
        sets = ', '.join(f'{c} = ?' for c in CAMPOS)
        valores = [_valor(c, datos) for c in CAMPOS]
        conn.execute(
            f'UPDATE solicitudes SET {sets}, updated_at = datetime("now", "localtime") WHERE id = ?',
            valores + [solicitud_id],
        )
        conn.execute('DELETE FROM items WHERE solicitud_id = ?', (solicitud_id,))
        _guardar_items(conn, solicitud_id, items)
        # facturas=None -> no se tocan (edicion que no cambia adjuntos); lista -> se reemplazan.
        if facturas is not None:
            conn.execute('DELETE FROM facturas WHERE solicitud_id = ?', (solicitud_id,))
            _guardar_facturas(conn, solicitud_id, facturas)
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


def _guardar_facturas(conn, solicitud_id, facturas):
    for i, f in enumerate(facturas or []):
        conn.execute(
            'INSERT INTO facturas (solicitud_id, nombre, archivo, numero, orden) '
            'VALUES (?, ?, ?, ?, ?)',
            (solicitud_id, f.get('nombre', ''), f.get('archivo', ''), f.get('numero', ''), i),
        )


def obtener(solicitud_id):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM solicitudes WHERE id = ?', (solicitud_id,)).fetchone()
        if not row:
            return None
        solicitud = _fila_a_dict(row)
        # Las listas se devuelven parseadas (con fallback al escalar de solicitudes viejas).
        solicitud['empresas'] = lista_multi(solicitud, 'empresas', 'empresa')
        solicitud['marcas'] = lista_multi(solicitud, 'marcas', 'marca')
        solicitud['items'] = [
            _fila_a_dict(r) for r in
            conn.execute('SELECT * FROM items WHERE solicitud_id = ? ORDER BY orden', (solicitud_id,))
        ]
        solicitud['facturas'] = [
            _fila_a_dict(r) for r in
            conn.execute('SELECT * FROM facturas WHERE solicitud_id = ? ORDER BY orden', (solicitud_id,))
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
        sql = ('SELECT s.*, '
               '(SELECT COUNT(*) FROM autorizaciones a WHERE a.solicitud_id = s.id) AS firmas, '
               '(SELECT COUNT(*) FROM facturas f WHERE f.solicitud_id = s.id) AS facturas '
               'FROM solicitudes s WHERE 1=1')
        params = []
        if estado:
            sql += ' AND s.estado = ?'
            params.append(estado)
        if busqueda:
            sql += (' AND (s.proveedor_nombre LIKE ? OR s.cuit LIKE ? OR s.marca LIKE ? '
                    'OR s.factura_numero LIKE ? OR s.solicitado_por LIKE ? '
                    'OR EXISTS (SELECT 1 FROM facturas f WHERE f.solicitud_id = s.id AND f.numero LIKE ?))')
            params += [f'%{busqueda}%'] * 6
        sql += ' ORDER BY s.id DESC'
        return [_fila_a_dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def eliminar(solicitud_id, motivo, eliminado_por=''):
    """Borra una solicitud dejando acta en 'eliminaciones' (qué, por qué y quién).
    El motivo es obligatorio. Devuelve (ok, error)."""
    motivo = str(motivo or '').strip()
    if not motivo:
        return False, 'Indicá el motivo de la eliminación'

    conn = get_db()
    try:
        s = conn.execute('SELECT * FROM solicitudes WHERE id = ?', (solicitud_id,)).fetchone()
        if not s:
            return False, 'La solicitud no existe'
        if s['estado'] == 'autorizada':
            return False, 'Una solicitud ya autorizada no se puede eliminar'
        firmas = conn.execute(
            'SELECT COUNT(*) AS n FROM autorizaciones WHERE solicitud_id = ?',
            (solicitud_id,)).fetchone()['n']

        conn.execute(
            'INSERT INTO eliminaciones (solicitud_id, proveedor_nombre, cuit, marca, empresa, '
            'monto_total, estado, fecha_factura, factura_numero, solicitado_por, firmas, '
            'motivo, eliminado_por) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (s['id'], s['proveedor_nombre'], s['cuit'], s['marca'], s['empresa'],
             s['monto_total'], s['estado'], s['fecha'], s['factura_numero'],
             s['solicitado_por'], firmas, motivo, str(eliminado_por or '').strip()),
        )
        conn.execute('DELETE FROM solicitudes WHERE id = ?', (solicitud_id,))
        conn.commit()
        return True, ''
    finally:
        conn.close()


def listar_eliminaciones():
    conn = get_db()
    try:
        return [_fila_a_dict(r) for r in
                conn.execute('SELECT * FROM eliminaciones ORDER BY id DESC')]
    finally:
        conn.close()


def marcas_de(solicitud):
    """Lista de marcas de una solicitud, sea dict o fila (con fallback al escalar)."""
    return lista_multi(dict(solicitud) if not isinstance(solicitud, dict) else solicitud,
                       'marcas', 'marca')


def autorizados_para(solicitud):
    """Autorizados habilitados para la(s) marca(s) de la solicitud, marcando quien excede
    su tope y quien ya firmó. Con varias marcas, solo quien las cubra todas."""
    listas = listas_habilitadas(marcas_de(solicitud))
    monto = float(solicitud['monto_total'] or 0)
    ya_firmaron = {a['nombre'] for a in solicitud['autorizaciones']}
    conn = get_db()
    try:
        placeholders = ', '.join('?' * len(listas))
        rows = conn.execute(
            f'SELECT id, nombre, cargo, lista, monto_autorizado, conceptos, bloqueado_hasta, '
            f'(pin_hash IS NOT NULL) AS tiene_pin FROM autorizados '
            f'WHERE activo = 1 AND lista IN ({placeholders}) ORDER BY lista, nombre', listas).fetchall()
    finally:
        conn.close()

    autorizados = []
    for r in rows:
        tope = r['monto_autorizado']
        bloqueado, minutos = esta_bloqueado(r['bloqueado_hasta'])
        autorizados.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'cargo': r['cargo'],
            'lista': r['lista'],
            'monto_autorizado': tope,
            'sin_limite': tope is None,
            'conceptos': r['conceptos'],
            'tiene_pin': bool(r['tiene_pin']),
            'bloqueado': bloqueado,
            'bloqueado_minutos': minutos,
            'excede_tope': tope is not None and monto > tope,
            'ya_firmo': r['nombre'] in ya_firmaron,
        })
    return autorizados
