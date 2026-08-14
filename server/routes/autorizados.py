from flask import Blueprint, jsonify, request

from models.database import get_db
from services.admin import requiere_admin, usando_default, verificar_admin
from services.pins import (
    esta_bloqueado, generar_codigo, hash_pin, registrar_intento, validar_pin, verificar_codigo,
    verificar_pin,
)

bp = Blueprint('autorizados', __name__)


@bp.route('/admin/verificar', methods=['POST'])
def verificar_clave_admin():
    """La usa el panel para desbloquear las acciones de administración por sesión."""
    data = request.get_json(silent=True) or {}
    if not verificar_admin(str(data.get('clave') or '')):
        return jsonify({'ok': False, 'error': 'Clave incorrecta'}), 401
    return jsonify({'ok': True, 'usando_default': usando_default()})


@bp.route('/autorizados', methods=['GET'])
def listar():
    """Listado de autorizados (las 4 planillas). Con ?todos=1 incluye a los dados de
    baja (para el panel de administración)."""
    lista = request.args.get('lista')
    incluir_inactivos = request.args.get('todos') == '1'
    conn = get_db()
    try:
        sql = ('SELECT id, nombre, cargo, lista, monto_autorizado, conceptos, bloqueado_hasta, '
               'activo, (pin_hash IS NOT NULL) AS tiene_pin, '
               '(codigo_alta_hash IS NOT NULL) AS alta_pendiente FROM autorizados WHERE 1=1')
        params = []
        if not incluir_inactivos:
            sql += ' AND activo = 1'
        if lista:
            sql += ' AND lista = ?'
            params.append(lista)
        sql += ' ORDER BY activo DESC, lista, nombre'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    salida = []
    for r in rows:
        bloqueado, minutos = esta_bloqueado(r['bloqueado_hasta'])
        salida.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'cargo': r['cargo'],
            'lista': r['lista'],
            'monto_autorizado': r['monto_autorizado'],
            'sin_limite': r['monto_autorizado'] is None,
            'conceptos': r['conceptos'],
            'activo': bool(r['activo']),
            'tiene_pin': bool(r['tiene_pin']),
            'alta_pendiente': bool(r['alta_pendiente']),
            'bloqueado': bloqueado,
            'bloqueado_minutos': minutos,
        })
    return jsonify(salida)


@bp.route('/autorizados/<int:autorizado_id>/activo', methods=['POST'])
@requiere_admin
def cambiar_activo(autorizado_id):
    """Da de baja (activo=0) o reactiva (activo=1) a un autorizante. La fila no se borra:
    se conserva el historial de lo que haya firmado. Un inactivo no aparece para firmar."""
    data = request.get_json(silent=True) or {}
    activo = 1 if data.get('activo') else 0
    conn = get_db()
    try:
        row = conn.execute('SELECT nombre FROM autorizados WHERE id = ?', (autorizado_id,)).fetchone()
        if not row:
            return jsonify({'error': 'El autorizado no existe'}), 404
        conn.execute('UPDATE autorizados SET activo = ? WHERE id = ?', (activo, autorizado_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True, 'activo': bool(activo), 'nombre': row['nombre']})


@bp.route('/autorizados/<int:autorizado_id>/codigo-alta', methods=['POST'])
@requiere_admin
def generar_codigo_alta(autorizado_id):
    """Genera el código de un solo uso para que la persona defina su PIN.
    El código se muestra UNA sola vez: administración se lo entrega en mano."""
    conn = get_db()
    try:
        row = conn.execute('SELECT nombre FROM autorizados WHERE id = ? AND activo = 1',
                           (autorizado_id,)).fetchone()
        if not row:
            return jsonify({'error': 'El autorizado no existe'}), 404

        codigo, codigo_hash = generar_codigo()
        conn.execute(
            'UPDATE autorizados SET codigo_alta_hash = ?, '
            'codigo_alta_fecha = datetime("now", "localtime"), '
            'intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?',
            (codigo_hash, autorizado_id))
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        'ok': True,
        'nombre': row['nombre'],
        'codigo': codigo,
        'aviso': 'Anotalo ahora: por seguridad no se vuelve a mostrar.',
    })


@bp.route('/autorizados/<int:autorizado_id>/pin', methods=['POST'])
def definir_pin(autorizado_id):
    """Alta o cambio de PIN.
      - Alta (todavía sin PIN): requiere el código que entregó administración.
      - Cambio: requiere el PIN actual.
    """
    data = request.get_json(silent=True) or {}
    pin_nuevo = str(data.get('pin_nuevo') or '')
    pin_actual = str(data.get('pin_actual') or '')
    codigo = str(data.get('codigo') or '')

    error_pin = validar_pin(pin_nuevo)
    if error_pin:
        return jsonify({'error': error_pin}), 400

    conn = get_db()
    try:
        a = conn.execute('SELECT * FROM autorizados WHERE id = ? AND activo = 1',
                         (autorizado_id,)).fetchone()
        if not a:
            return jsonify({'error': 'El autorizado no existe'}), 404

        bloqueado, minutos = esta_bloqueado(a['bloqueado_hasta'])
        if bloqueado:
            return jsonify({'error': f'Bloqueado por intentos fallidos. '
                                     f'Probá en {minutos} minuto(s).'}), 423

        if a['pin_hash']:
            # Ya tiene PIN: para cambiarlo hay que saber el actual.
            if codigo and not pin_actual:
                return jsonify({'error': 'Ese código de alta ya fue usado. Si querés cambiar '
                                         'tu PIN, ingresá el PIN actual.'}), 409
            if not verificar_pin(pin_actual, a['pin_hash']):
                registrar_intento(conn, autorizado_id, 'pin_incorrecto')
                conn.commit()
                return jsonify({'error': 'El PIN actual es incorrecto'}), 403
        else:
            # Alta: sin código válido no se puede definir el PIN de otra persona.
            if not a['codigo_alta_hash']:
                return jsonify({'error': 'No hay un código de alta generado. '
                                         'Pedíselo a administración.'}), 409
            if not verificar_codigo(codigo, a['codigo_alta_hash']):
                registrar_intento(conn, autorizado_id, 'codigo_invalido')
                conn.commit()
                return jsonify({'error': 'El código de alta no es correcto'}), 403

        conn.execute(
            'UPDATE autorizados SET pin_hash = ?, codigo_alta_hash = NULL, '
            'codigo_alta_fecha = NULL, intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?',
            (hash_pin(pin_nuevo), autorizado_id))
        registrar_intento(conn, autorizado_id, 'alta')
        conn.commit()
    finally:
        conn.close()

    return jsonify({'ok': True})


@bp.route('/autorizados/<int:autorizado_id>/pin', methods=['DELETE'])
@requiere_admin
def blanquear_pin(autorizado_id):
    """Blanqueo (reset admin): borra el PIN y entrega un código de alta nuevo, para
    que solo la persona pueda volver a definirlo."""
    conn = get_db()
    try:
        row = conn.execute('SELECT nombre FROM autorizados WHERE id = ? AND activo = 1',
                           (autorizado_id,)).fetchone()
        if not row:
            return jsonify({'error': 'El autorizado no existe'}), 404

        codigo, codigo_hash = generar_codigo()
        conn.execute(
            'UPDATE autorizados SET pin_hash = NULL, codigo_alta_hash = ?, '
            'codigo_alta_fecha = datetime("now", "localtime"), '
            'intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?',
            (codigo_hash, autorizado_id))
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        'ok': True,
        'nombre': row['nombre'],
        'codigo': codigo,
        'aviso': 'Entregale este código a la persona: lo necesita para definir su nuevo PIN.',
    })


@bp.route('/autorizados/<int:autorizado_id>/desbloquear', methods=['POST'])
@requiere_admin
def desbloquear(autorizado_id):
    """Levanta el bloqueo por intentos fallidos sin tocar el PIN."""
    conn = get_db()
    try:
        cur = conn.execute(
            'UPDATE autorizados SET intentos_fallidos = 0, bloqueado_hasta = NULL '
            'WHERE id = ? AND activo = 1', (autorizado_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'El autorizado no existe'}), 404
    finally:
        conn.close()
    return jsonify({'ok': True})


@bp.route('/autorizados/<int:autorizado_id>/intentos', methods=['GET'])
@requiere_admin
def intentos(autorizado_id):
    """Auditoría: últimos intentos de firma de esa persona."""
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT resultado, solicitud_id, fecha FROM intentos_pin '
            'WHERE autorizado_id = ? ORDER BY id DESC LIMIT 50', (autorizado_id,)).fetchall()
    finally:
        conn.close()
    return jsonify([{k: r[k] for k in r.keys()} for r in rows])
