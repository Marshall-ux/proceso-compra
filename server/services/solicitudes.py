"""Logica de negocio de las solicitudes (autorizaciones genericas)."""

import json
import re
from datetime import datetime

from models.database import get_db
from services import cuit as cuit_svc
from services import moneda as mon
from services.marcas import UBICACIONES, listas_habilitadas
from services.pins import esta_bloqueado

AUTORIZACIONES_REQUERIDAS = 2

CAMPOS = (
    'fecha', 'empresa', 'marca', 'marca_otro', 'proveedor_tipo', 'proveedor_nombre', 'cuit',
    'tipo_orden', 'duracion_orden', 'concepto', 'concepto_otro', 'monto_total', 'forma_pago',
    'cbu', 'condicion_pago', 'condicion_dias', 'condicion_otras', 'contacto_nombre',
    'contacto_telefono', 'contacto_mail', 'observaciones', 'solicitado_por', 'factura_nombre',
    'factura_archivo', 'factura_numero',
    # V2
    'criticidad', 'criticidad_obs', 'requiere_oc', 'cbu_imagen',
    'legajo_nombre', 'legajo_archivo',
    # Multi-selección (JSON)
    'empresas', 'marcas',
    # Moneda (ver services/moneda.py)
    'moneda', 'tipo_cambio',
    # Sede: con la razón social define a qué cajera se avisa (ver services/avisos.py)
    'ubicacion',
)

# Columnas numericas: se guardan como numero, no como texto.
CAMPOS_FLOAT = {'monto_total', 'tipo_cambio'}
# autopack_ok no va en CAMPOS: solo lo escribe la ruta del tilde, que exige la clave
# de Autopack (ver services/autopack.py). Así editar una solicitud no lo pisa.
CAMPOS_INT = set()

CRITICIDADES = ('urgente', 'informado', 'otro')

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


def formas_pago(valor):
    """forma_pago admite varias opciones: se guarda como texto separado por comas
    ("cheque,transferencia"). Acepta también una lista o el valor único viejo."""
    crudos = valor if isinstance(valor, list) else str(valor or '').split(',')
    salida = []
    for x in (str(x).strip() for x in crudos):
        if x and x not in salida:
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
        'forma_pago': ','.join(formas_pago(datos.get('forma_pago'))),
        'moneda': mon.normalizar(datos.get('moneda')),
        'cuit': cuit_svc.formatear(datos.get('cuit')),
        # En pesos el tipo de cambio no aplica: no queda uno viejo si se pasó de USD a ARS.
        'tipo_cambio': (mon.tipo_cambio(datos.get('tipo_cambio'))
                        if mon.normalizar(datos.get('moneda')) == 'USD' else 0),
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


def _vacio(datos, campo):
    return not str(datos.get(campo) or '').strip()


def validar_campos(datos):
    """Errores de la solicitud como (campo, mensaje), en el orden del formulario: la
    pantalla muestra cada uno al lado de su campo y lleva al primero."""
    errores = []

    def falta(campo, mensaje):
        errores.append((campo, mensaje))

    fecha = str(datos.get('fecha') or '').strip()
    if not fecha:
        falta('fecha', 'Falta la fecha de la factura')
    else:
        try:
            datetime.strptime(fecha, '%d/%m/%Y')
        except ValueError:
            falta('fecha', 'La fecha tiene que ser dd/mm/aaaa (por ejemplo, 05/11/2026)')
    if not lista_multi(datos, 'empresas', 'empresa'):
        falta('empresas', 'Seleccioná al menos una empresa a la que imputar el pago')
    marcas = lista_multi(datos, 'marcas', 'marca')
    if not marcas:
        falta('marcas', 'Seleccioná al menos una marca')
    elif 'OTRO' in marcas and _vacio(datos, 'marca_otro'):
        falta('marca_otro', 'Indicá cuál es la marca en "Otro"')
    # Sin ubicación no se sabe a qué cajera avisar cuando quede autorizada.
    if _vacio(datos, 'ubicacion'):
        falta('ubicacion', 'Elegí la ubicación (Rosario o Santa Fe)')
    elif datos.get('ubicacion') not in UBICACIONES:
        falta('ubicacion', 'Ubicación inválida')

    if _vacio(datos, 'proveedor_tipo'):
        falta('proveedor_tipo', 'Indicá si el proveedor es habitual o nuevo')
    if _vacio(datos, 'proveedor_nombre'):
        falta('proveedor_nombre', 'Falta el nombre del proveedor')
    if _vacio(datos, 'cuit'):
        falta('cuit', 'Falta el CUIT del proveedor')
    elif not cuit_svc.es_valido(datos.get('cuit')):
        falta('cuit', 'El CUIT no es válido: revisá los números (el último no coincide)')
    if _vacio(datos, 'tipo_orden'):
        falta('tipo_orden', 'Indicá si es una orden abierta o cerrada')
    elif datos.get('tipo_orden') == 'abierta' and _vacio(datos, 'duracion_orden'):
        falta('duracion_orden', 'Indicá la duración de la orden abierta')
    if datos.get('proveedor_tipo') == 'nuevo' and _vacio(datos, 'legajo_archivo'):
        falta('legajo_archivo', 'Al ser un proveedor nuevo, hay que adjuntar el legajo impositivo (PDF)')

    if _vacio(datos, 'criticidad'):
        falta('criticidad', 'Elegí qué tan urgente es el pago (criticidad)')
    elif datos.get('criticidad') not in CRITICIDADES:
        falta('criticidad', 'Criticidad inválida')
    elif datos.get('criticidad') == 'otro' and _vacio(datos, 'criticidad_obs'):
        falta('criticidad_obs', 'Indicá el detalle de la criticidad en "Otro"')
    if _vacio(datos, 'concepto'):
        falta('concepto', 'Elegí el concepto del pago')
    elif datos.get('concepto') == 'otros' and _vacio(datos, 'concepto_otro'):
        falta('concepto_otro', 'Indicá cuál es el concepto en "Otros"')

    try:
        monto = float(datos.get('monto_total') or 0)
    except (TypeError, ValueError):
        monto = 0
    if monto <= 0:
        falta('monto_total', 'El monto presupuesto final debe ser mayor a cero')
    if str(datos.get('moneda') or 'ARS').strip().upper() not in mon.MONEDAS:
        falta('moneda', 'Moneda inválida')
    elif mon.normalizar(datos.get('moneda')) == 'USD' and mon.tipo_cambio(datos.get('tipo_cambio')) <= 0:
        falta('tipo_cambio', 'En dólares hace falta el tipo de cambio (para comparar con los topes en pesos)')
    if ('transferencia' in formas_pago(datos.get('forma_pago'))
            and _vacio(datos, 'cbu') and _vacio(datos, 'cbu_imagen')):
        falta('cbu', 'Para transferencia hace falta el CBU (número o imagen)')
    if _vacio(datos, 'solicitado_por'):
        falta('solicitado_por', 'Falta quién solicita la compra o contratación')
    return errores


def validar(datos):
    """Los errores de `validar_campos`, solo los mensajes."""
    return [mensaje for _, mensaje in validar_campos(datos)]


def crear(datos, items, facturas=None, avisar_a=None):
    datos = _normalizar(datos)
    conn = get_db()
    try:
        # avisar_a va aparte de CAMPOS: editar solo lo cambia si se elige otro firmante.
        columnas = CAMPOS + ('avisar_a',)
        valores = [_valor(c, datos) for c in CAMPOS] + [json.dumps(avisar_a or [])]
        cur = conn.execute(
            f'INSERT INTO solicitudes ({", ".join(columnas)}) VALUES ({", ".join("?" * len(columnas))})',
            valores,
        )
        solicitud_id = cur.lastrowid
        _guardar_items(conn, solicitud_id, items)
        _guardar_facturas(conn, solicitud_id, facturas)
        conn.commit()
        return solicitud_id
    finally:
        conn.close()


def actualizar(solicitud_id, datos, items, facturas=None, avisar_a=None):
    """avisar_a=None deja el firmante como está; una lista lo reemplaza. Editar es
    también la forma de cambiar de firmante cuando el elegido ya no puede firmar."""
    conn = get_db()
    try:
        row = conn.execute('SELECT estado, avisar_a FROM solicitudes WHERE id = ?',
                           (solicitud_id,)).fetchone()
        if not row:
            return False, 'La solicitud no existe'
        if row['estado'] == 'autorizada':
            return False, 'La solicitud ya está autorizada y no se puede modificar'
        if row['estado'] == 'rechazada':
            return False, 'La solicitud está rechazada y no se puede modificar'
        datos = _normalizar(datos)
        # Si alguien ya firmó, editar cambiaría lo que firmó: se limpian las firmas.
        conn.execute('DELETE FROM autorizaciones WHERE solicitud_id = ?', (solicitud_id,))
        sets = ', '.join(f'{c} = ?' for c in CAMPOS)
        valores = [_valor(c, datos) for c in CAMPOS]
        conn.execute(
            f'UPDATE solicitudes SET {sets}, updated_at = datetime("now", "localtime") WHERE id = ?',
            valores + [solicitud_id],
        )
        if avisar_a is not None:
            conn.execute('UPDATE solicitudes SET avisar_a = ? WHERE id = ?',
                         (json.dumps(avisar_a), solicitud_id))
        # Una devuelta para corregir vuelve a firma al editarla. Si además cambió el
        # firmante, o vuelve de una devolución, le toca firmar desde ahora: los
        # recordatorios cuentan de nuevo (el mail lo manda la ruta).
        firmante_nuevo = avisar_a is not None and any(i not in ids_avisar_a(row) for i in avisar_a)
        if row['estado'] == 'observada' or firmante_nuevo:
            conn.execute(
                "UPDATE solicitudes SET estado = 'pendiente', "
                "aviso_firmante_at = datetime('now', 'localtime'), "
                'recordatorio1_at = NULL, recordatorio2_at = NULL WHERE id = ?', (solicitud_id,))
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
        solicitud['monto_pesos'] = monto_pesos(solicitud)
        solicitud['items'] = [
            _fila_a_dict(r) for r in
            conn.execute('SELECT * FROM items WHERE solicitud_id = ? ORDER BY orden', (solicitud_id,))
        ]
        solicitud['facturas'] = [
            _fila_a_dict(r) for r in
            conn.execute('SELECT * FROM facturas WHERE solicitud_id = ? AND pago_id IS NULL '
                         'ORDER BY orden', (solicitud_id,))
        ]
        ids = ids_avisar_a(solicitud)
        solicitud['avisar_a'] = ids
        solicitud['avisados'] = [
            r['nombre'] for r in conn.execute(
                f'SELECT nombre FROM autorizados WHERE id IN ({", ".join("?" * len(ids))}) '
                f'ORDER BY nombre', ids)
        ] if ids else []
        solicitud['autorizaciones'] = [
            _fila_a_dict(r) for r in conn.execute(
                'SELECT a.id, a.fecha, a.excedio_tope, a.monto_tope, au.nombre, au.cargo '
                'FROM autorizaciones a JOIN autorizados au ON au.id = a.autorizado_id '
                'WHERE a.solicitud_id = ? ORDER BY a.fecha', (solicitud_id,))
        ]
        firmas = solicitud['autorizaciones']
        autorizada = solicitud['estado'] == 'autorizada'
        # Segunda firma solo en las viejas sin firmante elegido: una firma que excedió el
        # tope las deja pendientes. Con firmante elegido hay una sola firma, que lo cubre.
        solicitud['requiere_segunda_firma'] = (not autorizada and len(firmas) == 1 and not ids)
        solicitud['autorizaciones_faltantes'] = 0 if autorizada else 1

        # Pagos imputados a esta AGC y devoluciones/rechazos del firmante (imports
        # diferidos para evitar ciclos).
        from services import pagos as pagos_svc
        from services import revisiones as revisiones_svc
        solicitud['revisiones'] = revisiones_svc.listar(conn, solicitud_id)
        solicitud['pagos'] = pagos_svc.listar_pagos(conn, solicitud_id)
        solicitud['pagos_resumen'] = pagos_svc.resumen(solicitud)
        return solicitud
    finally:
        conn.close()


# Filtros de la lista del inicio (y del Excel), tal como los manda la pantalla.
FILTROS = ('estado', 'q', 'empresa', 'marca', 'ubicacion', 'urgente', 'desde', 'hasta')
POR_PAGINA = 50
_FECHA_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')

_COLUMNAS_LISTA = (
    's.*, '
    '(SELECT COUNT(*) FROM autorizaciones a WHERE a.solicitud_id = s.id) AS firmas, '
    '(SELECT COUNT(*) FROM facturas f WHERE f.solicitud_id = s.id) AS facturas, '
    "(SELECT group_concat(au.nombre, ', ') FROM autorizaciones a "
    ' JOIN autorizados au ON au.id = a.autorizado_id WHERE a.solicitud_id = s.id) AS firmado_por, '
    # La última devolución o rechazo: quién y por qué (se ve en la lista).
    '(SELECT r.motivo FROM revisiones r WHERE r.solicitud_id = s.id '
    ' ORDER BY r.id DESC LIMIT 1) AS revision_motivo, '
    '(SELECT au.nombre FROM revisiones r JOIN autorizados au ON au.id = r.autorizado_id '
    ' WHERE r.solicitud_id = s.id ORDER BY r.id DESC LIMIT 1) AS revision_por'
)


def _donde(filtros):
    """WHERE de la lista según los filtros. Devuelve (sql, params). Las fechas `desde` y
    `hasta` son de carga (aaaa-mm-dd, como las da el calendario); una mal escrita se ignora."""
    f = {k: str(v or '').strip() for k, v in (filtros or {}).items()}
    sql, params = ' WHERE 1=1', []
    if f.get('estado'):
        sql += ' AND s.estado = ?'
        params.append(f['estado'])
    # empresas y marcas son JSON (multi-selección); empresa y marca, los escalares legacy.
    for lista, escalar in (('empresas', 'empresa'), ('marcas', 'marca')):
        if f.get(escalar):
            sql += f' AND (s.{lista} LIKE ? OR s.{escalar} = ?)'
            params += [f'%{json.dumps(f[escalar], ensure_ascii=False)}%', f[escalar]]
    if f.get('ubicacion'):
        sql += ' AND s.ubicacion = ?'
        params.append(f['ubicacion'])
    if f.get('urgente') in ('1', 'true', 'si'):
        sql += " AND s.criticidad = 'urgente'"
    if _FECHA_ISO.match(f.get('desde', '')):
        sql += ' AND date(s.created_at) >= date(?)'
        params.append(f['desde'])
    if _FECHA_ISO.match(f.get('hasta', '')):
        sql += ' AND date(s.created_at) <= date(?)'
        params.append(f['hasta'])
    if f.get('q'):
        sql += (' AND (s.proveedor_nombre LIKE ? OR s.cuit LIKE ? OR s.marca LIKE ? '
                'OR s.factura_numero LIKE ? OR s.solicitado_por LIKE ? '
                'OR s.empresa LIKE ? OR s.empresas LIKE ? '
                'OR EXISTS (SELECT 1 FROM facturas f WHERE f.solicitud_id = s.id AND f.numero LIKE ?))')
        params += [f'%{f["q"]}%'] * 8
    return sql, params


def listar(filtros=None, pagina=1, por_pagina=POR_PAGINA):
    """Lista del inicio, filtrada y de a una página, de la más nueva a la más vieja
    (`por_pagina=None` trae todas, para el Excel). Cada fila trae además `firmante` (a
    quién espera: el firmante elegido; vacío en las viejas, que firma cualquier
    habilitado), `firmado_por` y la última devolución o rechazo.
    Devuelve {'solicitudes', 'total', 'pagina', 'por_pagina'}."""
    donde, params = _donde(filtros)
    try:
        pagina = max(1, int(pagina or 1))
    except (TypeError, ValueError):
        pagina = 1
    sql = f'SELECT {_COLUMNAS_LISTA} FROM solicitudes s{donde} ORDER BY s.id DESC'
    paginado = list(params)
    if por_pagina:
        sql += ' LIMIT ? OFFSET ?'
        paginado += [por_pagina, (pagina - 1) * por_pagina]
    conn = get_db()
    try:
        total = conn.execute(f'SELECT COUNT(*) AS n FROM solicitudes s{donde}', params).fetchone()['n']
        nombres = {r['id']: r['nombre'] for r in conn.execute('SELECT id, nombre FROM autorizados')}
        filas = []
        for r in conn.execute(sql, paginado):
            d = _fila_a_dict(r)
            d['firmante'] = ', '.join(nombres[i] for i in ids_avisar_a(d) if i in nombres)
            filas.append(d)
    finally:
        conn.close()
    return {'solicitudes': filas, 'total': total, 'pagina': pagina, 'por_pagina': por_pagina}


def para_firmar(autorizado_id):
    """Solicitudes pendientes que le tocan a este autorizante: habilitado para la
    marca, que todavía no firmó y que es el firmante que eligió quien cargó el gasto,
    con tope que cubre el monto (las mismas reglas que `autorizacion.firmar`).
    Ordenadas por urgencia (las urgentes primero) y después de la última cargada
    a la primera.

    Las cargadas antes de que se eligiera firmante no tienen ninguno: esas se le
    muestran a todos los habilitados, que son quienes pueden firmarlas."""
    conn = get_db()
    try:
        a = conn.execute('SELECT lista, monto_autorizado FROM autorizados WHERE id = ? AND activo = 1',
                         (autorizado_id,)).fetchone()
        if not a:
            return []
        salida = []
        for s in conn.execute("SELECT * FROM solicitudes WHERE estado = 'pendiente' ORDER BY id DESC"):
            listas = listas_habilitadas(marcas_de(s))
            if a['lista'] not in listas:
                continue
            firmaron = {r['autorizado_id'] for r in conn.execute(
                'SELECT autorizado_id FROM autorizaciones WHERE solicitud_id = ?', (s['id'],))}
            if autorizado_id in firmaron:
                continue
            elegidos = ids_avisar_a(s)
            if elegidos and autorizado_id not in elegidos:
                continue
            # Si su tope ya no cubre el monto no puede firmarla (autorizacion.firmar): no se
            # le lista. La solicitud se destraba editándola y eligiendo otro firmante.
            tope = a['monto_autorizado']
            if elegidos and tope is not None and monto_pesos(s) > tope:
                continue
            firmas = len(firmaron)
            d = _fila_a_dict(s)
            d['marcas'] = marcas_de(s)
            d['firmas'] = firmas
            d['requiere_segunda_firma'] = (firmas == 1 and not elegidos)
            salida.append(d)
        # urgentes primero; dentro de cada grupo, de la última cargada a la primera.
        salida.sort(key=lambda x: (x.get('created_at') or '', x['id']), reverse=True)
        salida.sort(key=lambda x: x.get('criticidad') != 'urgente')
        return salida
    finally:
        conn.close()


def eliminar(solicitud_id, motivo, eliminado_por='', es_admin=False):
    """Borra una solicitud dejando acta en 'eliminaciones' (qué, por qué y quién).
    El motivo es obligatorio. Una solicitud autorizada o rechazada (que queda como
    registro) solo la puede eliminar administración (es_admin). Devuelve (ok, error)."""
    motivo = str(motivo or '').strip()
    if not motivo:
        return False, 'Indicá el motivo de la eliminación'

    conn = get_db()
    try:
        s = conn.execute('SELECT * FROM solicitudes WHERE id = ?', (solicitud_id,)).fetchone()
        if not s:
            return False, 'La solicitud no existe'
        if s['estado'] in ('autorizada', 'rechazada') and not es_admin:
            return False, (f'Una solicitud {s["estado"]} solo la puede eliminar administración '
                           f'(con la clave)')
        firmas = conn.execute(
            'SELECT COUNT(*) AS n FROM autorizaciones WHERE solicitud_id = ?',
            (solicitud_id,)).fetchone()['n']

        conn.execute(
            'INSERT INTO eliminaciones (solicitud_id, proveedor_nombre, cuit, marca, empresa, '
            'monto_total, moneda, estado, fecha_factura, factura_numero, solicitado_por, firmas, '
            'motivo, eliminado_por) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (s['id'], s['proveedor_nombre'], s['cuit'], s['marca'], s['empresa'],
             s['monto_total'], s['moneda'], s['estado'], s['fecha'], s['factura_numero'],
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


def monto_pesos(solicitud):
    """Monto de la solicitud en pesos (en dólares, con su tipo de cambio): es lo que
    se compara con los topes de los autorizantes."""
    return mon.en_pesos(solicitud['monto_total'], solicitud['moneda'], solicitud['tipo_cambio'])


def marcas_de(solicitud):
    """Lista de marcas de una solicitud, sea dict o fila (con fallback al escalar)."""
    return lista_multi(dict(solicitud) if not isinstance(solicitud, dict) else solicitud,
                       'marcas', 'marca')


def autorizados_para(solicitud):
    """Autorizados habilitados para la(s) marca(s) de la solicitud, marcando quien excede
    su tope, quien ya firmó y quien puede firmarla (el firmante elegido; en las
    solicitudes viejas sin elegido, cualquiera). Con varias marcas, solo quien las
    cubra todas."""
    listas = listas_habilitadas(marcas_de(solicitud))
    monto = monto_pesos(solicitud)
    ya_firmaron = {a['nombre'] for a in solicitud['autorizaciones']}
    elegidos = ids_avisar_a(solicitud)
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
            'puede_firmar': not elegidos or r['id'] in elegidos,
        })
    return autorizados


def ids_avisar_a(solicitud):
    """Ids de los autorizados a los que se les aviso del gasto (JSON en la columna)."""
    crudo = solicitud.get('avisar_a') if isinstance(solicitud, dict) else solicitud['avisar_a']
    if isinstance(crudo, list):
        return crudo
    try:
        valor = json.loads(crudo or '[]')
    except ValueError:
        return []
    return [int(x) for x in valor if str(x).isdigit()] if isinstance(valor, list) else []


def candidatos_aviso(marcas, monto):
    """A quien se le puede mandar el aviso de un gasto: los habilitados para la(s)
    marca(s) que ademas pueden cerrarlo solos por monto (tope suficiente o sin limite).
    El monto va en pesos (si el gasto es en dólares, ya convertido).

    Quien carga la solicitud elige de esta lista. Van primero los de la planilla de la
    marca y despues Multimarca, que es la que cubre todo.
    TODO concepto: cuando administracion pase que categorias firma cada uno, se filtra
    tambien por el concepto del gasto.
    """
    listas = listas_habilitadas(marcas)
    try:
        monto = float(monto or 0)
    except (TypeError, ValueError):
        monto = 0.0
    conn = get_db()
    try:
        marcadores = ', '.join('?' * len(listas))
        rows = conn.execute(
            f'SELECT id, nombre, cargo, lista, monto_autorizado, email FROM autorizados '
            f'WHERE activo = 1 AND lista IN ({marcadores}) '
            f'AND (monto_autorizado IS NULL OR monto_autorizado >= ?)', listas + [monto]).fetchall()
    finally:
        conn.close()
    candidatos = [{
        'id': r['id'],
        'nombre': r['nombre'],
        'cargo': r['cargo'],
        'lista': r['lista'],
        'monto_autorizado': r['monto_autorizado'],
        'sin_limite': r['monto_autorizado'] is None,
        'tiene_mail': '@' in (r['email'] or ''),
    } for r in rows]
    candidatos.sort(key=lambda c: (c['lista'] == 'multimarca', c['lista'], c['nombre']))
    return candidatos


def validar_avisar_a(datos):
    """Quien carga la solicitud TIENE que elegir al firmante, y uno solo: el aviso
    le llega exclusivamente a esa persona. Ni toda la planilla ni varios a la vez,
    para que no queden dos personas mirando el mismo gasto sin saber quien lo firma.

    Devuelve (ids, errores); ids es una lista de un elemento (la columna sigue
    siendo una lista JSON por las solicitudes viejas, que tienen varios). Se
    revalida contra los candidatos del servidor: el navegador pudo quedar con una
    lista vieja (cambio la marca o el monto)."""
    crudos = datos.get('avisar_a') or []
    if not isinstance(crudos, list):
        crudos = [crudos]
    ids = []
    for x in crudos:
        try:
            i = int(x)
        except (TypeError, ValueError):
            continue
        if i not in ids:
            ids.append(i)
    if not ids:
        return [], ['Elegí quién tiene que firmar esta solicitud (le llega el aviso por mail)']
    if len(ids) > 1:
        return ids, ['Elegí un solo firmante: el aviso le llega solo a esa persona']

    marcas = lista_multi(datos, 'marcas', 'marca')
    pesos = mon.en_pesos(datos.get('monto_total'), datos.get('moneda'), datos.get('tipo_cambio'))
    candidatos = {c['id']: c for c in candidatos_aviso(marcas, pesos)}
    errores = []
    for i in ids:
        c = candidatos.get(i)
        if not c:
            errores.append('El firmante elegido no puede firmar este gasto '
                           '(por marca o por monto). Revisá la selección.')
            break
        if not c['tiene_mail']:
            errores.append(f'{c["nombre"]} no tiene mail cargado: elegí a otra persona '
                           f'o pedile a administración que lo cargue.')
    return ids, errores
