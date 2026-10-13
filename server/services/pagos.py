"""Pagos imputados a una AGC ya autorizada.

La AGC controla el presupuesto; cada pago (anticipo/avance de una obra, viaje de un
flete, etc.) se firma como conformidad de que el servicio/avance se dio. Los pagos no
re-autorizan la AGC. Misma regla de firma que la AGC: alcanza 1 firma si el monto del
pago no supera el tope de quien firma; si lo supera, hace falta una 2a.
"""

from models.database import get_db
from services import moneda as mon
from services.marcas import listas_habilitadas
from services.solicitudes import AUTORIZACIONES_REQUERIDAS, marcas_de


def _dict(row):
    return {k: row[k] for k in row.keys()}


def crear_pago(solicitud_id, datos, facturas):
    """Crea un pago imputado a una AGC autorizada. Devuelve (pago_id, error)."""
    monto = 0.0
    try:
        monto = float(datos.get('monto') or 0)
    except (TypeError, ValueError):
        monto = 0.0
    if monto <= 0:
        return None, 'El monto del pago debe ser mayor a cero'

    conn = get_db()
    try:
        s = conn.execute('SELECT estado, moneda FROM solicitudes WHERE id = ?',
                         (solicitud_id,)).fetchone()
        if not s:
            return None, 'La AGC no existe'
        if s['estado'] != 'autorizada':
            return None, 'Solo se pueden imputar pagos a una AGC ya autorizada'
        # El pago va en la moneda de la AGC; en dólares, con el tipo de cambio del día
        # del pago (para controlar el tope de quien firma la conformidad).
        cambio = 0.0
        if mon.normalizar(s['moneda']) == 'USD':
            cambio = mon.tipo_cambio(datos.get('tipo_cambio'))
            if cambio <= 0:
                return None, 'La AGC es en dólares: indicá el tipo de cambio del pago'

        cur = conn.execute(
            'INSERT INTO pagos (solicitud_id, descripcion, monto, fecha, cargado_por, tipo_cambio) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (solicitud_id, str(datos.get('descripcion') or '').strip(), monto,
             str(datos.get('fecha') or '').strip(), str(datos.get('cargado_por') or '').strip(),
             cambio))
        pago_id = cur.lastrowid
        for i, f in enumerate(facturas or []):
            conn.execute(
                'INSERT INTO facturas (solicitud_id, nombre, archivo, numero, orden, pago_id) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (solicitud_id, f.get('nombre', ''), f.get('archivo', ''), f.get('numero', ''),
                 i, pago_id))
        conn.commit()
        return pago_id, ''
    finally:
        conn.close()


def listar_pagos(conn, solicitud_id):
    """Pagos de una AGC, con sus facturas y firmas. Usa una conexión ya abierta."""
    pagos = []
    for p in conn.execute('SELECT * FROM pagos WHERE solicitud_id = ? ORDER BY id', (solicitud_id,)):
        d = _dict(p)
        d['facturas'] = [_dict(r) for r in conn.execute(
            'SELECT * FROM facturas WHERE pago_id = ? ORDER BY orden', (p['id'],))]
        d['firmas'] = [_dict(r) for r in conn.execute(
            'SELECT pf.id, pf.fecha, pf.excedio_tope, pf.monto_tope, au.nombre, au.cargo '
            'FROM pago_firmas pf JOIN autorizados au ON au.id = pf.autorizado_id '
            'WHERE pf.pago_id = ? ORDER BY pf.fecha', (p['id'],))]
        d['requiere_segunda_firma'] = (d['estado'] != 'conforme' and len(d['firmas']) == 1)
        pagos.append(d)
    return pagos


def resumen(solicitud):
    """Presupuesto vs imputado vs saldo. En orden abierta el monto es tarifario de
    referencia: el acumulado puede superarlo y NO se marca como exceso."""
    presupuesto = float(solicitud.get('monto_total') or 0)
    imputado = sum(float(p.get('monto') or 0) for p in solicitud.get('pagos', []))
    abierta = solicitud.get('tipo_orden') == 'abierta'
    return {
        'moneda': mon.normalizar(solicitud.get('moneda')),
        'presupuesto': presupuesto,
        'imputado': round(imputado, 2),
        'saldo': round(presupuesto - imputado, 2),
        'abierta': abierta,
        'excede': (not abierta) and imputado > presupuesto,
    }


def firmar_pago(conn, solicitud, pago, autorizado):
    """Registra una firma de conformidad. Misma regla que la AGC.
    Devuelve (ok, motivo, excedio_tope). Asume el autorizante ya verificado (PIN)."""
    if pago['estado'] == 'conforme':
        return False, 'El pago ya está conforme', False

    if autorizado['lista'] not in listas_habilitadas(marcas_de(solicitud)):
        return False, f'{autorizado["nombre"]} no está habilitado para la marca de esta AGC', False

    ya = conn.execute('SELECT 1 FROM pago_firmas WHERE pago_id = ? AND autorizado_id = ?',
                      (pago['id'], autorizado['id'])).fetchone()
    if ya:
        return False, f'{autorizado["nombre"]} ya firmó este pago', False

    tope = autorizado['monto_autorizado']
    # Los topes están en pesos: un pago en dólares se compara con su tipo de cambio.
    excedio = tope is not None and mon.en_pesos(pago['monto'], solicitud['moneda'],
                                                pago['tipo_cambio']) > tope
    conn.execute(
        'INSERT INTO pago_firmas (pago_id, autorizado_id, excedio_tope, monto_tope) '
        'VALUES (?, ?, ?, ?)', (pago['id'], autorizado['id'], 1 if excedio else 0, tope))

    n = conn.execute('SELECT COUNT(*) AS n FROM pago_firmas WHERE pago_id = ?',
                     (pago['id'],)).fetchone()['n']
    # Alcanza 1 firma dentro del tope; si lo supera, hace falta una 2a.
    if n >= AUTORIZACIONES_REQUERIDAS or (n == 1 and not excedio):
        conn.execute('UPDATE pagos SET estado = "conforme" WHERE id = ?', (pago['id'],))

    return True, '', excedio


def obtener_pago(conn, solicitud_id, pago_id):
    row = conn.execute('SELECT * FROM pagos WHERE id = ? AND solicitud_id = ?',
                       (pago_id, solicitud_id)).fetchone()
    return _dict(row) if row else None


def eliminar_pago(solicitud_id, pago_id):
    """Elimina un pago mientras no esté conforme. Devuelve (ok, error)."""
    conn = get_db()
    try:
        p = conn.execute('SELECT estado FROM pagos WHERE id = ? AND solicitud_id = ?',
                         (pago_id, solicitud_id)).fetchone()
        if not p:
            return False, 'El pago no existe'
        if p['estado'] == 'conforme':
            return False, 'El pago ya está conforme; no se puede eliminar'
        conn.execute('DELETE FROM facturas WHERE pago_id = ?', (pago_id,))
        conn.execute('DELETE FROM pago_firmas WHERE pago_id = ?', (pago_id,))
        conn.execute('DELETE FROM pagos WHERE id = ?', (pago_id,))
        conn.commit()
        return True, ''
    finally:
        conn.close()
