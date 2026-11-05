import logging
import os
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from models.database import get_db
from services import autopack
from services import avisos
from services import ordenes_abiertas
from services import pagos
from services import proveedores
from services import revisiones
from services import solicitudes as svc
from services.admin import verificar_admin
from services.autorizacion import (
    ErrorAutorizante, firmar, motivo_no_pendiente, verificar_autorizante,
)
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

UPLOADS =os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')


def _invalida(errores_campos, errores_aviso):
    """400 con los errores: la lista y, por campo, el primero de cada uno (la pantalla
    los muestra al lado de su campo y lleva al primero)."""
    campos = {}
    for campo, mensaje in errores_campos:
        campos.setdefault(campo, mensaje)
    if errores_aviso:
        campos.setdefault('avisar_a', errores_aviso[0])
    return jsonify({'error': 'Faltan datos obligatorios',
                    'errores': [m for _, m in errores_campos] + errores_aviso,
                    'campos': campos}), 400


def _con_disponibles(solicitud):
    """Agrega la lista de autorizados habilitados (para los selectores de firma) y
    quiénes pueden cambiar el tipo de orden."""
    if solicitud:
        solicitud['autorizados_disponibles'] = svc.autorizados_para(solicitud)
        conn = get_db()
        try:
            solicitud['habilitados_tipo_orden'] = ordenes_abiertas.habilitados(conn)
        finally:
            conn.close()
    return solicitud


@bp.route('/solicitudes', methods=['GET'])
def listar():
    return jsonify(svc.listar(estado=request.args.get('estado'),
                              busqueda=request.args.get('q'),
                              empresa=request.args.get('empresa')))


@bp.route('/solicitudes/para-firmar', methods=['GET'])
def para_firmar():
    """Pendientes que un autorizante puede firmar (para el acceso rápido del firmante)."""
    try:
        autorizado_id = int(request.args.get('autorizado_id'))
    except (TypeError, ValueError):
        return jsonify([])
    return jsonify(svc.para_firmar(autorizado_id))


@bp.route('/solicitudes/abiertas-similares', methods=['GET'])
def abiertas_similares():
    """Órdenes abiertas del mismo CUIT, marca y concepto: la pantalla de alta pregunta
    si la factura nueva es de alguna de ellas antes de crear otra solicitud."""
    conn = get_db()
    try:
        return jsonify(ordenes_abiertas.similares(
            conn, request.args.get('cuit'), request.args.getlist('marca'),
            request.args.get('concepto')))
    finally:
        conn.close()


@bp.route('/proveedores/<cuit>', methods=['GET'])
def proveedor(cuit):
    """Datos de un proveedor tomados de sus solicitudes anteriores (por CUIT): el alta
    los completa solos."""
    return jsonify(proveedores.datos_previos(cuit))


@bp.route('/solicitudes/<int:solicitud_id>/tipo-orden', methods=['POST'])
def cambiar_tipo_orden(solicitud_id):
    """Pasa una solicitud pendiente a orden abierta o cerrada. Solo los habilitados
    (ver services/ordenes_abiertas.py), con su PIN; queda registrado quién y cuándo."""
    data = request.get_json(silent=True) or {}
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404

    conn = get_db()
    try:
        try:
            autorizado = verificar_autorizante(conn, data.get('autorizado_id'),
                                               str(data.get('pin') or ''), solicitud_id)
        except ErrorAutorizante as e:
            return jsonify({'error': e.mensaje, **e.extra}), e.codigo
        ok, error = ordenes_abiertas.cambiar_tipo(
            conn, solicitud, autorizado, data.get('tipo_orden'), data.get('duracion_orden'))
        if not ok:
            conn.commit()   # el PIN correcto ya reseteó los intentos fallidos
            return jsonify({'error': error}), 400
        conn.commit()
    finally:
        conn.close()
    return jsonify(_con_disponibles(svc.obtener(solicitud_id)))


@bp.route('/solicitudes', methods=['POST'])
def crear():
    data = request.get_json(silent=True) or {}
    errores_campos = svc.validar_campos(data)
    avisar_a, errores_aviso = svc.validar_avisar_a(data)
    if errores_campos or errores_aviso:
        return _invalida(errores_campos, errores_aviso)
    solicitud_id = svc.crear(data, data.get('items', []), data.get('facturas', []), avisar_a)
    # El gasto nace pendiente: recien ACA, ya persistido, se avisa a los autorizantes.
    solicitud = svc.obtener(solicitud_id)
    _avisar(avisos.notificar_gasto_a_autorizar, solicitud)
    return jsonify(solicitud), 201


@bp.route('/solicitudes/<int:solicitud_id>', methods=['GET'])
def obtener(solicitud_id):
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    return jsonify(_con_disponibles(solicitud))


@bp.route('/solicitudes/<int:solicitud_id>', methods=['PUT'])
def actualizar(solicitud_id):
    """Edita una solicitud pendiente. El firmante se vuelve a validar contra la marca
    y el monto editados (pueden haber dejado al elegido sin poder firmarla), y editar
    es también como se cambia de firmante si el elegido ya no puede (baja, tope)."""
    data = request.get_json(silent=True) or {}
    previa = svc.obtener(solicitud_id)
    if not previa:
        return jsonify({'error': 'La solicitud no existe'}), 404
    errores_campos = svc.validar_campos(data)
    avisar_a, errores_aviso = svc.validar_avisar_a(data)
    if errores_campos or errores_aviso:
        return _invalida(errores_campos, errores_aviso)
    ok, error = svc.actualizar(solicitud_id, data, data.get('items', []), data.get('facturas'),
                               avisar_a=avisar_a)
    if not ok:
        return jsonify({'error': error}), 400
    solicitud = svc.obtener(solicitud_id)
    # Mail solo si el firmante es alguien que no estaba avisado: al editar una vieja
    # con varios avisados y quedarse con uno de ellos, esa persona ya tenía el mail.
    if any(i not in previa['avisar_a'] for i in avisar_a):
        _avisar(avisos.notificar_cambio_firmante, solicitud)
    elif previa['estado'] == 'observada':
        # La corrigieron: vuelve a firma y el firmante que la devolvió se entera.
        _avisar(avisos.notificar_corregida, solicitud)
    return jsonify(solicitud)


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
    """Registra la firma del firmante elegido, que la deja autorizada (su tope tiene que
    cubrir el monto). Las viejas sin firmante siguen con la regla de la segunda firma
    (ver services/autorizacion.py)."""
    data = request.get_json(silent=True) or {}
    pin = str(data.get('pin') or '')

    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404
    if solicitud['estado'] != 'pendiente':
        return jsonify({'error': motivo_no_pendiente(solicitud['estado'])}), 400

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
    _con_disponibles(resultado)
    resultado['aviso_tope'] = (
        f'{nombre} autorizó un monto que supera su tope de '
        f'$ {fmt_money(tope)}. Queda registrado en el PDF.' if excedio else ''
    )
    return jsonify(resultado)


@bp.route('/solicitudes/<int:solicitud_id>/revisar', methods=['POST'])
def revisar(solicitud_id):
    """El firmante la devuelve para corregir (accion=observar) o la rechaza
    (accion=rechazar), con su PIN y un motivo. Ver services/revisiones.py."""
    data = request.get_json(silent=True) or {}
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404

    conn = get_db()
    try:
        try:
            autorizado = verificar_autorizante(conn, data.get('autorizado_id'),
                                               str(data.get('pin') or ''), solicitud_id)
        except ErrorAutorizante as e:
            return jsonify({'error': e.mensaje, **e.extra}), e.codigo
        ok, error = revisiones.revisar(conn, solicitud, autorizado, data.get('accion'),
                                       data.get('motivo'))
        conn.commit()   # aunque no se pueda, el PIN correcto ya reseteó los intentos fallidos
        if not ok:
            return jsonify({'error': error}), 400
    finally:
        conn.close()
    return jsonify(_con_disponibles(svc.obtener(solicitud_id)))


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


@bp.route('/autopack/verificar', methods=['POST'])
def verificar_autopack():
    """La usa la lista para abrir la sesión de Autopack (una vez por pestaña)."""
    data = request.get_json(silent=True) or {}
    nombre = autopack.identificar(data.get('email'), data.get('clave'))
    if not nombre:
        return jsonify({'error': 'Mail no habilitado para Autopack o clave incorrecta'}), 401
    return jsonify({'ok': True, 'nombre': nombre})


@bp.route('/solicitudes/<int:solicitud_id>/autopack', methods=['POST'])
def marcar_autopack(solicitud_id):
    """Tilde de 'cargado en Autopack', para que administración no se saltee el paso
    de cargar la operación en el otro sistema. Solo lo tilda administración
    (headers X-Autopack-Email / X-Autopack-Password) y queda registrado quién."""
    nombre = autopack.identificar(request.headers.get('X-Autopack-Email'),
                                  request.headers.get('X-Autopack-Password'))
    if not nombre:
        return jsonify({'error': 'Solo administración puede tildar Autopack: '
                                 'ingresá tu mail y la clave'}), 401
    data = request.get_json(silent=True) or {}
    valor = 1 if data.get('ok') else 0
    conn = get_db()
    try:
        cur = conn.execute(
            'UPDATE solicitudes SET autopack_ok = ?, autopack_por = ?, '
            'autopack_fecha = datetime("now", "localtime"), '
            'updated_at = datetime("now", "localtime") WHERE id = ?',
            (valor, nombre, solicitud_id))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'La solicitud no existe'}), 404
        row = conn.execute('SELECT autopack_por, autopack_fecha FROM solicitudes WHERE id = ?',
                           (solicitud_id,)).fetchone()
    finally:
        conn.close()
    return jsonify({'ok': True, 'autopack_ok': valor,
                    'autopack_por': row['autopack_por'], 'autopack_fecha': row['autopack_fecha']})


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
    """Firma la conformidad de un pago (que el servicio/avance se dio). La firma
    cualquier habilitado para la marca: 1 firma dentro del tope, 2 si lo supera."""
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
    _con_disponibles(resultado)
    return jsonify(resultado)


@bp.route('/solicitudes/<int:solicitud_id>/pdf', methods=['GET'])
def pdf(solicitud_id):
    """PDF de la autorización genérica. Se puede ver en cualquier momento (con marca de
    pendiente) y es el entregable final cuando ya firmaron los dos."""
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404

    return send_file(generar_pdf(solicitud), mimetype='application/pdf', as_attachment=False,
                     download_name=f'Autorizacion-Generica-{solicitud_id}.pdf')


@bp.route('/solicitudes/<int:solicitud_id>/pdf-completo', methods=['GET'])
def pdf_completo(solicitud_id):
    """Autorización + facturas en un solo PDF, para imprimir todo junto."""
    solicitud = svc.obtener(solicitud_id)
    if not solicitud:
        return jsonify({'error': 'La solicitud no existe'}), 404

    rutas = []
    for f in solicitud['facturas']:
        ruta = os.path.normpath(os.path.join(UPLOADS, f['archivo'] or ''))
        if ruta.startswith(os.path.normpath(UPLOADS)) and os.path.exists(ruta):
            rutas.append((f['nombre'], ruta))

    completo, _ = generar_pdf_con_facturas(generar_pdf(solicitud), rutas)
    return send_file(completo, mimetype='application/pdf', as_attachment=False,
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
