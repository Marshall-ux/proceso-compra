import os

from flask import Blueprint, jsonify, request, send_file

from models.database import get_db
from services import solicitudes as svc
from services.pdf_fill import fmt_money, generar_pdf
from services.pins import hash_pin, pin_valido, verificar_pin

bp = Blueprint('solicitudes', __name__)

GENERADOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'generated')
UPLOADS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')


@bp.route('/solicitudes', methods=['GET'])
def listar():
    return jsonify(svc.listar(estado=request.args.get('estado'),
                              busqueda=request.args.get('q')))


@bp.route('/solicitudes', methods=['POST'])
def crear():
    data = request.get_json(silent=True) or {}
    errores = svc.validar(data)
    if errores:
        return jsonify({'error': 'Faltan datos obligatorios', 'errores': errores}), 400
    solicitud_id = svc.crear(data, data.get('items', []), data.get('facturas', []))
    return jsonify(svc.obtener(solicitud_id)), 201


@bp.route('/solicitudes/<int:solicitud_id>', methods=['GET'])
def obtener(solicitud_id):
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    solicitud['autorizados_disponibles'] = svc.autorizados_para(solicitud)
    return jsonify(solicitud)


@bp.route('/solicitudes/<int:solicitud_id>', methods=['PUT'])
def actualizar(solicitud_id):
    data = request.get_json(silent=True) or {}
    errores = svc.validar(data)
    if errores:
        return jsonify({'error': 'Faltan datos obligatorios', 'errores': errores}), 400
    ok, error = svc.actualizar(solicitud_id, data, data.get('items', []), data.get('facturas'))
    if not ok:
        return jsonify({'error': error}), 400
    return jsonify(svc.obtener(solicitud_id))


@bp.route('/solicitudes/<int:solicitud_id>', methods=['DELETE'])
def eliminar(solicitud_id):
    if not svc.eliminar(solicitud_id):
        return jsonify({'error': 'La solicitud no existe'}), 404
    return jsonify({'ok': True})


@bp.route('/solicitudes/<int:solicitud_id>/autorizar', methods=['POST'])
def autorizar(solicitud_id):
    """Registra la firma de un autorizado. Hacen falta dos personas distintas para
    que la solicitud quede autorizada."""
    data = request.get_json(silent=True) or {}
    autorizado_id = data.get('autorizado_id')
    pin = str(data.get('pin') or '')
    pin_nuevo = str(data.get('pin_nuevo') or '')

    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    if solicitud['estado'] == 'autorizada':
        return jsonify({'error': 'La solicitud ya está autorizada'}), 400

    conn = get_db()
    try:
        autorizado = conn.execute(
            'SELECT * FROM autorizados WHERE id = ? AND activo = 1', (autorizado_id,)).fetchone()
        if not autorizado:
            return jsonify({'error': 'El autorizado no existe'}), 404

        # La marca de la solicitud tiene que estar dentro de la planilla del autorizado.
        habilitados = {a['id'] for a in svc.autorizados_para(solicitud)}
        if autorizado['id'] not in habilitados:
            return jsonify({'error': f'{autorizado["nombre"]} no está habilitado para autorizar '
                                     f'compras de la marca {solicitud["marca"]}'}), 403

        # Primera vez que firma: da de alta su PIN.
        if not autorizado['pin_hash']:
            if not pin_valido(pin_nuevo):
                return jsonify({'error': 'primer_uso',
                                'mensaje': f'{autorizado["nombre"]} todavía no tiene PIN. '
                                           f'Definí uno de 4 a 6 dígitos.'}), 409
            conn.execute('UPDATE autorizados SET pin_hash = ? WHERE id = ?',
                         (hash_pin(pin_nuevo), autorizado['id']))
            conn.commit()
        elif not verificar_pin(pin, autorizado['pin_hash']):
            return jsonify({'error': 'PIN incorrecto'}), 403

        # Dos firmas, dos personas: la misma no puede firmar dos veces.
        ya = conn.execute(
            'SELECT 1 FROM autorizaciones WHERE solicitud_id = ? AND autorizado_id = ?',
            (solicitud_id, autorizado['id'])).fetchone()
        if ya:
            return jsonify({'error': f'{autorizado["nombre"]} ya autorizó esta solicitud. '
                                     f'Hacen falta dos personas distintas.'}), 400

        tope = autorizado['monto_autorizado']
        excedio = tope is not None and float(solicitud['monto_total'] or 0) > tope

        conn.execute(
            'INSERT INTO autorizaciones (solicitud_id, autorizado_id, excedio_tope, monto_tope) '
            'VALUES (?, ?, ?, ?)', (solicitud_id, autorizado['id'], 1 if excedio else 0, tope))

        firmas = conn.execute('SELECT COUNT(*) AS n FROM autorizaciones WHERE solicitud_id = ?',
                              (solicitud_id,)).fetchone()['n']
        if firmas >= svc.AUTORIZACIONES_REQUERIDAS:
            conn.execute('UPDATE solicitudes SET estado = "autorizada", '
                         'updated_at = datetime("now", "localtime") WHERE id = ?', (solicitud_id,))
        conn.commit()
    finally:
        conn.close()

    resultado = svc.obtener(solicitud_id)
    resultado['autorizados_disponibles'] = svc.autorizados_para(resultado)
    resultado['aviso_tope'] = (
        f'{autorizado["nombre"]} autorizó un monto que supera su tope de '
        f'$ {fmt_money(tope)}. Queda registrado en el PDF.' if excedio else ''
    )
    return jsonify(resultado)


@bp.route('/solicitudes/<int:solicitud_id>/autorizaciones/<int:autorizacion_id>', methods=['DELETE'])
def quitar_autorizacion(solicitud_id, autorizacion_id):
    """Deshace una firma (solo mientras la solicitud siga pendiente)."""
    conn = get_db()
    try:
        row = conn.execute('SELECT estado FROM solicitudes WHERE id = ?', (solicitud_id,)).fetchone()
        if not row:
            return jsonify({'error': 'La solicitud no existe'}), 404
        if row['estado'] == 'autorizada':
            return jsonify({'error': 'La solicitud ya está autorizada; no se pueden quitar firmas'}), 400
        conn.execute('DELETE FROM autorizaciones WHERE id = ? AND solicitud_id = ?',
                     (autorizacion_id, solicitud_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify(svc.obtener(solicitud_id))


@bp.route('/solicitudes/<int:solicitud_id>/pdf', methods=['GET'])
def pdf(solicitud_id):
    """PDF de la autorización genérica. Se puede ver en cualquier momento (con marca de
    pendiente) y es el entregable final cuando ya firmaron los dos."""
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404

    os.makedirs(GENERADOS, exist_ok=True)
    destino = os.path.join(GENERADOS, f'autorizacion-{solicitud_id}.pdf')
    generar_pdf(solicitud, destino)
    return send_file(destino, mimetype='application/pdf', as_attachment=False,
                     download_name=f'Autorizacion-Generica-{solicitud_id}.pdf')


def _adjunto(archivo, nombre_descarga, mimetype):
    """Sirve un archivo de uploads/ validando que exista y no escape del directorio."""
    if not archivo:
        return jsonify({'error': 'No hay archivo adjunto'}), 404
    ruta = os.path.normpath(os.path.join(UPLOADS, archivo))
    if not ruta.startswith(os.path.normpath(UPLOADS)) or not os.path.exists(ruta):
        return jsonify({'error': 'El archivo no está disponible'}), 404
    return send_file(ruta, mimetype=mimetype, download_name=nombre_descarga)


@bp.route('/solicitudes/<int:solicitud_id>/facturas/<int:factura_id>', methods=['GET'])
def factura(solicitud_id, factura_id):
    """Devuelve el PDF original de una de las facturas de la solicitud."""
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    fac = next((f for f in solicitud['facturas'] if f['id'] == factura_id), None)
    if not fac:
        return jsonify({'error': 'La factura no existe'}), 404
    return _adjunto(fac['archivo'], fac['nombre'] or 'factura.pdf', 'application/pdf')


@bp.route('/solicitudes/<int:solicitud_id>/cbu-imagen', methods=['GET'])
def cbu_imagen(solicitud_id):
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    ext = os.path.splitext(solicitud['cbu_imagen'])[1].lower()
    mime = 'image/png' if ext == '.png' else 'image/jpeg'
    return _adjunto(solicitud['cbu_imagen'], f'CBU-{solicitud_id}{ext}', mime)


@bp.route('/solicitudes/<int:solicitud_id>/legajo', methods=['GET'])
def legajo(solicitud_id):
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    return _adjunto(solicitud['legajo_archivo'],
                    solicitud['legajo_nombre'] or f'Legajo-{solicitud_id}.pdf', 'application/pdf')
