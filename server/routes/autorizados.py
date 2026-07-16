from flask import Blueprint, jsonify, request

from models.database import get_db
from services.pins import hash_pin, pin_valido, verificar_pin

bp = Blueprint('autorizados', __name__)


@bp.route('/autorizados', methods=['GET'])
def listar():
    """Listado completo de autorizados (las 4 planillas)."""
    lista = request.args.get('lista')
    conn = get_db()
    try:
        sql = ('SELECT id, nombre, cargo, lista, monto_autorizado, conceptos, '
               '(pin_hash IS NOT NULL) AS tiene_pin FROM autorizados WHERE activo = 1')
        params = []
        if lista:
            sql += ' AND lista = ?'
            params.append(lista)
        sql += ' ORDER BY lista, nombre'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return jsonify([{
        'id': r['id'],
        'nombre': r['nombre'],
        'cargo': r['cargo'],
        'lista': r['lista'],
        'monto_autorizado': r['monto_autorizado'],
        'sin_limite': r['monto_autorizado'] is None,
        'conceptos': r['conceptos'],
        'tiene_pin': bool(r['tiene_pin']),
    } for r in rows])


@bp.route('/autorizados/<int:autorizado_id>/pin', methods=['POST'])
def definir_pin(autorizado_id):
    """Alta o cambio de PIN. Para cambiarlo hay que saber el actual."""
    data = request.get_json(silent=True) or {}
    pin_nuevo = str(data.get('pin_nuevo') or '')
    pin_actual = str(data.get('pin_actual') or '')

    if not pin_valido(pin_nuevo):
        return jsonify({'error': 'El PIN debe tener entre 4 y 6 dígitos'}), 400

    conn = get_db()
    try:
        row = conn.execute('SELECT pin_hash FROM autorizados WHERE id = ? AND activo = 1',
                           (autorizado_id,)).fetchone()
        if not row:
            return jsonify({'error': 'El autorizado no existe'}), 404
        if row['pin_hash'] and not verificar_pin(pin_actual, row['pin_hash']):
            return jsonify({'error': 'El PIN actual es incorrecto'}), 403

        conn.execute('UPDATE autorizados SET pin_hash = ? WHERE id = ?',
                     (hash_pin(pin_nuevo), autorizado_id))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'ok': True})
