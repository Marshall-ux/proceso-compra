import os
import uuid

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from services.extractor import extraer_datos_factura

bp = Blueprint('facturas', __name__)

UPLOADS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')

# Campos de texto que se toman de la primera factura que los traiga.
_CAMPOS_PRIMERO = (
    'fecha', 'empresa', 'proveedor_nombre', 'cuit', 'condicion_pago', 'condicion_dias',
    'contacto_mail', 'contacto_telefono', 'cbu',
)


def _guardar_pdf(archivo):
    os.makedirs(UPLOADS, exist_ok=True)
    nombre_original = secure_filename(archivo.filename)
    nombre_guardado = f'{uuid.uuid4().hex}.pdf'
    archivo.save(os.path.join(UPLOADS, nombre_guardado))
    return nombre_original, nombre_guardado


def _guardar_archivo(archivo, extensiones):
    """Guarda un adjunto validando su extension. Devuelve (nombre_original, nombre_guardado)
    o (None, None) si la extension no es válida."""
    nombre_original = secure_filename(archivo.filename)
    ext = os.path.splitext(nombre_original)[1].lower()
    if ext not in extensiones:
        return None, None
    os.makedirs(UPLOADS, exist_ok=True)
    nombre_guardado = f'{uuid.uuid4().hex}{ext}'
    archivo.save(os.path.join(UPLOADS, nombre_guardado))
    return nombre_original, nombre_guardado


@bp.route('/archivos/cbu', methods=['POST'])
def subir_cbu():
    """Imagen del CBU (JPG/PNG)."""
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return jsonify({'error': 'No se recibió ningún archivo'}), 400
    nombre, guardado = _guardar_archivo(archivo, {'.jpg', '.jpeg', '.png'})
    if not guardado:
        return jsonify({'error': 'La imagen del CBU debe ser JPG o PNG'}), 400
    return jsonify({'nombre': nombre, 'archivo': guardado})


@bp.route('/archivos/legajo', methods=['POST'])
def subir_legajo():
    """Legajo impositivo (PDF)."""
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return jsonify({'error': 'No se recibió ningún archivo'}), 400
    nombre, guardado = _guardar_archivo(archivo, {'.pdf'})
    if not guardado:
        return jsonify({'error': 'El legajo debe ser un PDF'}), 400
    return jsonify({'nombre': nombre, 'archivo': guardado})


@bp.route('/facturas/extraer', methods=['POST'])
def extraer():
    """Recibe uno o varios PDF de factura y devuelve UNA sola orden combinada:
    los ítems se concatenan y los montos se suman. Cada archivo queda registrado
    aparte para adjuntarlo a la solicitud."""
    archivos = request.files.getlist('archivos') or request.files.getlist('archivo')
    archivos = [a for a in archivos if a and a.filename]
    if not archivos:
        return jsonify({'error': 'No se recibió ningún archivo'}), 400
    if any(not a.filename.lower().endswith('.pdf') for a in archivos):
        return jsonify({'error': 'Todos los archivos deben ser PDF'}), 400

    datos = {}
    items = []
    facturas = []
    empresas = []       # empresas detectadas (una factura por empresa del grupo)
    monto_total = 0.0
    ilegibles = []

    for archivo in archivos:
        nombre_original, nombre_guardado = _guardar_pdf(archivo)
        ruta = os.path.join(UPLOADS, nombre_guardado)
        try:
            resultado = extraer_datos_factura(ruta)
        except Exception:
            resultado = {'ok': False, 'datos': {}, 'items': []}

        d = resultado.get('datos', {}) or {}
        # El primer valor no vacío gana para los datos de cabecera.
        for campo in _CAMPOS_PRIMERO:
            if not datos.get(campo) and d.get(campo):
                datos[campo] = d[campo]
        if d.get('empresa') and d['empresa'] not in empresas:
            empresas.append(d['empresa'])
        monto_total += float(d.get('monto_total') or 0)
        items.extend(resultado.get('items', []) or [])
        facturas.append({
            'nombre': nombre_original,
            'archivo': nombre_guardado,
            'numero': d.get('factura_numero', ''),
        })
        if not resultado.get('ok'):
            ilegibles.append(nombre_original)

    datos['monto_total'] = round(monto_total, 2)
    # Compatibilidad: el primer numero de factura queda tambien en el campo legacy.
    datos['factura_numero'] = facturas[0]['numero'] if facturas else ''
    # Multi-empresa: se pre-tildan las empresas detectadas en las facturas.
    datos['empresas'] = empresas
    datos['empresa'] = empresas[0] if empresas else ''

    faltantes = ['marca', 'concepto', 'proveedor_tipo', 'tipo_orden', 'solicitado_por', 'criticidad']
    faltantes += [k for k in ('fecha', 'empresa', 'proveedor_nombre', 'cuit') if not datos.get(k)]

    error = ''
    if ilegibles:
        error = ('No se pudo leer el texto de: ' + ', '.join(ilegibles) +
                 '. Revisá y completá los datos a mano.')

    return jsonify({
        'ok': not ilegibles,
        'error': error,
        'datos': datos,
        'items': items,
        'facturas': facturas,
        'faltantes': faltantes,
    })
