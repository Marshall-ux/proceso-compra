import logging
import os
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from models.database import get_db
from services import avisos
from services import pagos
from services import solicitudes as svc
from services.admin import verificar_admin
from services.autorizacion import ErrorAutorizante, firmar, verificar_autorizante
from services.paquete import armar_zip, armar_zip_lote, nombre_zip
from services.pdf_fill import fmt_money, generar_pdf, generar_pdf_con_facturas

log = logging.getLogger(__name__)

bp = Blueprint('solicitudes', __name__)


def _avisar(fn, solicitud):
    """Dispara un aviso por mail sin que su fallo voltee la operacion: el mail es
    un extra, la solicitud ya esta guardada. Si no sale, queda en el log."""
    try:
        fn(solicitud, request)
    except Exception:
        log.exception('Fallo el aviso por mail de la solicitud #%s', solicitud.get('id'))

GENERADOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'generated')
UPLOADS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')


def _con_disponibles(solicitud):
    """Agrega la lista de autorizados habilitados (para los selectores de firma)."""
    if solicitud:
        solicitud['autorizados_disponibles'] = svc.autorizados_para(solicitud)
    return solicitud


@bp.route('/solicitudes', methods=['GET'])
def listar():
    return jsonify(svc.listar(estado=request.args.get('estado'),
                              busqueda=request.args.get('q')))


@bp.route('/solicitudes/para-firmar', methods=['GET'])
def para_firmar():
    """Pendientes que un autorizante puede firmar (para el acceso rápido del firmante)."""
    try:
        autorizado_id = int(request.args.get('autorizado_id'))
    except (TypeError, ValueError):
        return jsonify([])
    return jsonify(svc.para_firmar(autorizado_id))


@bp.route('/solicitudes', methods=['POST'])
def crear():
    data = request.get_json(silent=True) or {}
    errores = svc.validar(data)
    if errores:
        return jsonify({'error': 'Faltan datos obligatorios', 'errores': errores}), 400
    solicitud_id = svc.crear(data, data.get('items', []), data.get('facturas', []))
    # El gasto nace pendiente: recien ACA, ya persistido, se avisa a los autorizantes.
    solicitud = svc.obtener(solicitud_id)
    _avisar(avisos.notificar_gasto_a_autorizar, solicitud)
    return jsonify(solicitud), 201


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
    """Elimina la solicitud dejando acta del motivo. El motivo es obligatorio. Las ya
    autorizadas solo las puede eliminar administración (clave X-Admin-Password)."""
    data = request.get_json(silent=True) or {}
    es_admin = verificar_admin(request.headers.get('X-Admin-Password', ''))
    ok, error = svc.eliminar(solicitud_id, data.get('motivo'), data.get('eliminado_por'),
                             es_admin=es_admin)
    if not ok:
        if error == 'La solicitud no existe':
            codigo = 404
        elif 'administración' in error:
            codigo = 403
        else:
            codigo = 400
        return jsonify({'error': error}), codigo
    return jsonify({'ok': True})


@bp.route('/eliminaciones', methods=['GET'])
def eliminaciones():
    """Registro de solicitudes eliminadas: qué, por qué, quién y cuándo."""
    return jsonify(svc.listar_eliminaciones())


@bp.route('/solicitudes/<int:solicitud_id>/autorizar', methods=['POST'])
def autorizar(solicitud_id):
    """Registra la firma de un autorizado. Hacen falta dos personas distintas para
    que la solicitud quede autorizada."""
    data = request.get_json(silent=True) or {}
    pin = str(data.get('pin') or '')

    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    if solicitud['estado'] == 'autorizada':
        return jsonify({'error': 'La solicitud ya está autorizada'}), 400

    conn = get_db()
    try:
        try:
            autorizado = verificar_autorizante(conn, data.get('autorizado_id'), pin, solicitud_id)
        except ErrorAutorizante as e:
            return jsonify({'error': e.mensaje, **e.extra}), e.codigo

        ok, motivo, excedio = firmar(conn, solicitud, autorizado)
        if not ok:
            conn.commit()
            return jsonify({'error': motivo}), 400
        conn.commit()
        nombre, tope = autorizado['nombre'], autorizado['monto_autorizado']
    finally:
        conn.close()

    resultado = svc.obtener(solicitud_id)
    # Si esta firma completo la autorizacion, administracion ya puede pagarla.
    _avisar(avisos.notificar_autorizada, resultado)
    resultado['autorizados_disponibles'] = svc.autorizados_para(resultado)
    resultado['aviso_tope'] = (
        f'{nombre} autorizó un monto que supera su tope de '
        f'$ {fmt_money(tope)}. Queda registrado en el PDF.' if excedio else ''
    )
    return jsonify(resultado)


@bp.route('/solicitudes/autorizar-lote', methods=['POST'])
def autorizar_lote():
    """Firma varias solicitudes de una vez: el PIN se pide una sola vez, pero las
    reglas (marca habilitada, no firmar dos veces, ya autorizada) se aplican una
    por una. Devuelve qué se firmó y qué se salteó, con el motivo."""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    pin = str(data.get('pin') or '')
    if not ids:
        return jsonify({'error': 'No se recibió ninguna solicitud'}), 400

    conn = get_db()
    try:
        try:
            autorizado = verificar_autorizante(conn, data.get('autorizado_id'), pin)
        except ErrorAutorizante as e:
            return jsonify({'error': e.mensaje, **e.extra}), e.codigo

        firmadas, salteadas, avisos = [], [], []
        for sid in ids:
            solicitud = conn.execute('SELECT * FROM solicitudes WHERE id = ?', (sid,)).fetchone()
            if not solicitud:
                salteadas.append({'id': sid, 'motivo': 'No existe'})
                continue
            ok, motivo, excedio = firmar(conn, solicitud, autorizado)
            if ok:
                firmadas.append(sid)
                if excedio:
                    avisos.append(f'Solicitud #{sid}: supera el tope de '
                                  f'$ {fmt_money(autorizado["monto_autorizado"])}.')
            else:
                salteadas.append({'id': sid, 'motivo': motivo})
        conn.commit()
        nombre = autorizado['nombre']
    finally:
        conn.close()

    for sid in firmadas:
        _avisar(avisos.notificar_autorizada, svc.obtener(sid))

    return jsonify({
        'ok': True,
        'autorizante': nombre,
        'firmadas': firmadas,
        'salteadas': salteadas,
        'avisos': avisos,
        'resumen': f'{nombre} firmó {len(firmadas)} de {len(ids)} solicitudes.',
    })


@bp.route('/solicitudes/<int:solicitud_id>/autopack', methods=['POST'])
def marcar_autopack(solicitud_id):
    """Tilde de 'cargado en Autopack', para que administración no se saltee el paso
    de cargar la operación en el otro sistema."""
    data = request.get_json(silent=True) or {}
    valor = 1 if data.get('ok') else 0
    conn = get_db()
    try:
        cur = conn.execute(
            'UPDATE solicitudes SET autopack_ok = ?, updated_at = datetime("now", "localtime") '
            'WHERE id = ?', (valor, solicitud_id))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'La solicitud no existe'}), 404
    finally:
        conn.close()
    return jsonify({'ok': True, 'autopack_ok': valor})


# ------------------------------- pagos imputados ----------------------------
@bp.route('/solicitudes/<int:solicitud_id>/pagos', methods=['POST'])
def crear_pago(solicitud_id):
    """Imputa un pago (factura de anticipo/avance/servicio) a una AGC ya autorizada."""
    data = request.get_json(silent=True) or {}
    pago_id, error = pagos.crear_pago(solicitud_id, data, data.get('facturas', []))
    if error:
        codigo = 404 if 'no existe' in error else 400
        return jsonify({'error': error}), codigo
    return jsonify(_con_disponibles(svc.obtener(solicitud_id))), 201


@bp.route('/solicitudes/<int:solicitud_id>/pagos/<int:pago_id>/firmar', methods=['POST'])
def firmar_pago(solicitud_id, pago_id):
    """Firma la conformidad de un pago (que el servicio/avance se dio). Misma regla que
    la AGC: 1 firma dentro del tope, 2 si lo supera."""
    data = request.get_json(silent=True) or {}
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La AGC no existe'}), 404

    conn = get_db()
    try:
        pago = pagos.obtener_pago(conn, solicitud_id, pago_id)
        if not pago:
            return jsonify({'error': 'El pago no existe'}), 404
        try:
            autorizado = verificar_autorizante(conn, data.get('autorizado_id'), str(data.get('pin') or ''))
        except ErrorAutorizante as e:
            return jsonify({'error': e.mensaje, **e.extra}), e.codigo

        ok, motivo, excedio = pagos.firmar_pago(conn, solicitud, pago, autorizado)
        if not ok:
            conn.commit()
            return jsonify({'error': motivo}), 400
        conn.commit()
        nombre, tope = autorizado['nombre'], autorizado['monto_autorizado']
    finally:
        conn.close()

    resultado = _con_disponibles(svc.obtener(solicitud_id))
    resultado['aviso_tope'] = (
        f'{nombre} firmó un pago que supera su tope de $ {fmt_money(tope)}: '
        f'hace falta una segunda firma.' if excedio else ''
    )
    return jsonify(resultado)


@bp.route('/solicitudes/<int:solicitud_id>/pagos/<int:pago_id>', methods=['DELETE'])
def eliminar_pago(solicitud_id, pago_id):
    """Elimina un pago mientras no esté conforme."""
    ok, error = pagos.eliminar_pago(solicitud_id, pago_id)
    if not ok:
        codigo = 404 if 'no existe' in error else 400
        return jsonify({'error': error}), codigo
    return jsonify(_con_disponibles(svc.obtener(solicitud_id)))


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
    resultado = svc.obtener(solicitud_id)
    resultado['autorizados_disponibles'] = svc.autorizados_para(resultado)
    return jsonify(resultado)


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


@bp.route('/solicitudes/<int:solicitud_id>/pdf-completo', methods=['GET'])
def pdf_completo(solicitud_id):
    """Autorización + facturas en un solo PDF, para imprimir todo junto."""
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404

    os.makedirs(GENERADOS, exist_ok=True)
    autorizacion = os.path.join(GENERADOS, f'autorizacion-{solicitud_id}.pdf')
    generar_pdf(solicitud, autorizacion)

    rutas = []
    for f in solicitud['facturas']:
        ruta = os.path.normpath(os.path.join(UPLOADS, f['archivo'] or ''))
        if ruta.startswith(os.path.normpath(UPLOADS)) and os.path.exists(ruta):
            rutas.append((f['nombre'], ruta))

    destino = os.path.join(GENERADOS, f'autorizacion-completa-{solicitud_id}.pdf')
    generar_pdf_con_facturas(autorizacion, rutas, destino)
    return send_file(destino, mimetype='application/pdf', as_attachment=False,
                     download_name=f'Autorizacion-{solicitud_id}-con-facturas.pdf')


@bp.route('/solicitudes/<int:solicitud_id>/zip', methods=['GET'])
def zip_solicitud(solicitud_id):
    """Todo lo de la solicitud en un ZIP, para archivar en el disco interno."""
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    return send_file(armar_zip(solicitud), mimetype='application/zip',
                     as_attachment=True, download_name=nombre_zip(solicitud))


@bp.route('/solicitudes/zip', methods=['GET'])
def zip_lote():
    """ZIP con varias solicitudes (?ids=1,2,3), cada una en su carpeta."""
    crudos = request.args.get('ids', '')
    ids = [int(x) for x in crudos.split(',') if x.strip().isdigit()]
    if not ids:
        return jsonify({'error': 'Indicá qué solicitudes descargar'}), 400

    solicitudes = [s for s in (svc.obtener(i) for i in ids) if s]
    if not solicitudes:
        return jsonify({'error': 'Ninguna de esas solicitudes existe'}), 404

    nombre = f'Solicitudes-{datetime.now().strftime("%Y-%m-%d")}-{len(solicitudes)}.zip'
    return send_file(armar_zip_lote(solicitudes), mimetype='application/zip',
                     as_attachment=True, download_name=nombre)


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
    """Devuelve el PDF de una factura de la solicitud (de la AGC o de un pago)."""
    conn = get_db()
    try:
        fac = conn.execute('SELECT nombre, archivo FROM facturas WHERE id = ? AND solicitud_id = ?',
                           (factura_id, solicitud_id)).fetchone()
    finally:
        conn.close()
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
