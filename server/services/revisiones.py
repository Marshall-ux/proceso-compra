"""Devolver para corregir y rechazar: lo que puede hacer el firmante cuando no está de
acuerdo con una solicitud, en vez de firmarla.

- Devolver (queda `observada`): vuelve a quien la cargó para que la corrija. Cuando
  alguien la edita, vuelve a pendiente y al firmante le llega el mail de nuevo.
- Rechazar (queda `rechazada`): definitivo. No se firma ni se edita; queda en la lista
  como registro (y solo administración la puede eliminar).

Lo hace quien puede firmarla (el firmante elegido; en las viejas sin elegido,
cualquier habilitado para la marca), con su PIN y con motivo obligatorio. No se avisa
por mail a quien la cargó: la app no tiene su mail, y se decidió que el estado y el
motivo se vean solo en la app (lista y detalle).
"""

from services.marcas import listas_habilitadas
from services.solicitudes import ids_avisar_a, marcas_de

ACCIONES = {'observar': 'observada', 'rechazar': 'rechazada'}


def revisar(conn, solicitud, autorizado, accion, motivo):
    """Devuelve o rechaza la solicitud. Asume el autorizante ya verificado (PIN).
    Devuelve (ok, error)."""
    estado = ACCIONES.get(accion)
    if not estado:
        return False, 'Acción inválida'
    motivo = str(motivo or '').strip()
    if not motivo:
        return False, ('Contá qué hay que corregir' if accion == 'observar'
                       else 'Contá por qué se rechaza')

    actual = solicitud['estado']
    if actual == 'autorizada':
        return False, 'La solicitud ya está autorizada'
    if actual == 'rechazada':
        return False, 'La solicitud ya está rechazada'
    if actual == 'observada' and accion == 'observar':
        return False, 'La solicitud ya está devuelta para corregir'

    if autorizado['lista'] not in listas_habilitadas(marcas_de(solicitud)):
        return False, f'{autorizado["nombre"]} no está habilitado para la marca de esta solicitud'
    elegidos = ids_avisar_a(solicitud)
    if elegidos and autorizado['id'] not in elegidos:
        return False, (f'{autorizado["nombre"]} no es el firmante de esta solicitud: '
                       f'solo quien la tiene que firmar puede devolverla o rechazarla')

    conn.execute(
        'INSERT INTO revisiones (solicitud_id, autorizado_id, accion, motivo) VALUES (?, ?, ?, ?)',
        (solicitud['id'], autorizado['id'], estado, motivo))
    conn.execute('UPDATE solicitudes SET estado = ?, updated_at = datetime("now", "localtime") '
                 'WHERE id = ?', (estado, solicitud['id']))
    return True, ''


def listar(conn, solicitud_id):
    """Devoluciones y rechazos de una solicitud, del primero al último."""
    return [{k: r[k] for k in r.keys()} for r in conn.execute(
        'SELECT r.id, r.accion, r.motivo, r.fecha, au.nombre FROM revisiones r '
        'JOIN autorizados au ON au.id = r.autorizado_id WHERE r.solicitud_id = ? ORDER BY r.id',
        (solicitud_id,))]
