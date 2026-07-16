import os
import uuid

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from services.extractor import extraer_datos_factura

bp = Blueprint('facturas', __name__)

UPLOADS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')


@bp.route('/facturas/extraer', methods=['POST'])
def extraer():
    """Recibe el PDF de la factura, lo guarda y devuelve los datos que se pudieron leer."""
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return jsonify({'error': 'No se recibió ningún archivo'}), 400
    if not archivo.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'El archivo debe ser un PDF'}), 400

    os.makedirs(UPLOADS, exist_ok=True)
    nombre_original = secure_filename(archivo.filename)
    nombre_guardado = f'{uuid.uuid4().hex}.pdf'
    ruta = os.path.join(UPLOADS, nombre_guardado)
    archivo.save(ruta)

    try:
        resultado = extraer_datos_factura(ruta)
    except Exception as e:  # PDF corrupto o ilegible: se completa a mano
        return jsonify({
            'ok': False,
            'error': f'No se pudo leer el PDF ({e}). Cargá los datos a mano.',
            'datos': {}, 'items': [], 'faltantes': [],
            'factura_nombre': nombre_original, 'factura_archivo': nombre_guardado,
        }), 200

    resultado['factura_nombre'] = nombre_original
    resultado['factura_archivo'] = nombre_guardado
    return jsonify(resultado)
