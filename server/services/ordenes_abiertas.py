"""Órdenes abiertas: evitar que se cargue dos veces la misma y quién puede marcarlas.

Una orden abierta (flete, servicio recurrente) se autoriza una vez y después se le
imputan las facturas como pagos. Si al mes siguiente alguien carga la factura como una
solicitud nueva, se duplica la orden: por eso al guardar se buscan órdenes abiertas del
mismo proveedor (CUIT), marca y concepto, y se pregunta si es la misma.
"""

import re

from services.solicitudes import marcas_de

# Quiénes pueden cambiar una solicitud pendiente a orden abierta o cerrada, con su PIN.
# Nombre tal como figura en la tabla de autorizados.
HABILITADOS_TIPO_ORDEN = ('Raul Garcia',)

TIPOS = ('abierta', 'cerrada')


def solo_digitos(cuit):
    return re.sub(r'\D', '', str(cuit or ''))


def similares(conn, cuit, marcas, concepto, excluir_id=None):
    """Órdenes abiertas (pendientes o autorizadas) con el mismo CUIT, alguna marca en
    común y el mismo concepto. Sin CUIT o sin concepto no se busca: no hay con qué
    comparar sin dar falsos avisos."""
    cuit = solo_digitos(cuit)
    marcas = {m for m in (marcas or []) if m}
    if not cuit or not concepto or not marcas:
        return []
    salida = []
    for s in conn.execute(
            "SELECT * FROM solicitudes WHERE tipo_orden = 'abierta' AND concepto = ? "
            'ORDER BY id DESC', (concepto,)):
        if s['id'] == excluir_id or solo_digitos(s['cuit']) != cuit:
            continue
        marcas_s = marcas_de(s)
        if not marcas & set(marcas_s):
            continue
        salida.append({
            'id': s['id'],
            'proveedor_nombre': s['proveedor_nombre'],
            'cuit': s['cuit'],
            'marcas': marcas_s,
            'concepto': s['concepto'],
            'fecha': s['fecha'],
            'duracion_orden': s['duracion_orden'],
            'monto_total': s['monto_total'],
            'moneda': s['moneda'],
            'estado': s['estado'],
            'created_at': s['created_at'],
        })
    return salida


def habilitados(conn):
    """Autorizados activos que pueden cambiar el tipo de orden (para el selector)."""
    placeholders = ', '.join('?' * len(HABILITADOS_TIPO_ORDEN))
    return [{'id': r['id'], 'nombre': r['nombre'], 'tiene_pin': bool(r['tiene_pin'])}
            for r in conn.execute(
                f'SELECT id, nombre, (pin_hash IS NOT NULL) AS tiene_pin FROM autorizados '
                f'WHERE activo = 1 AND nombre IN ({placeholders}) ORDER BY nombre',
                HABILITADOS_TIPO_ORDEN)]


def cambiar_tipo(conn, solicitud, autorizado, tipo, duracion):
    """Cambia el tipo de orden de una solicitud pendiente. Si ya tenía firmas se borran:
    cambia lo que sale en el PDF y nadie firma algo que después se modificó (igual que
    al editar). Devuelve (ok, error)."""
    if autorizado['nombre'] not in HABILITADOS_TIPO_ORDEN:
        return False, f'{autorizado["nombre"]} no está habilitado para cambiar el tipo de orden'
    if solicitud['estado'] == 'autorizada':
        return False, 'La solicitud ya está autorizada: el tipo de orden no se puede cambiar'
    if tipo not in TIPOS:
        return False, 'Tipo de orden inválido'
    duracion = str(duracion or '').strip()
    if tipo == 'abierta' and not duracion:
        return False, 'Indicá la duración de la orden abierta'
    if tipo == 'cerrada':
        duracion = ''
    conn.execute('DELETE FROM autorizaciones WHERE solicitud_id = ?', (solicitud['id'],))
    conn.execute(
        'UPDATE solicitudes SET tipo_orden = ?, duracion_orden = ?, tipo_orden_por = ?, '
        'tipo_orden_fecha = datetime("now", "localtime"), '
        'updated_at = datetime("now", "localtime") WHERE id = ?',
        (tipo, duracion, autorizado['nombre'], solicitud['id']))
    return True, ''
