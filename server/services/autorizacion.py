"""Verificación del autorizante y registro de firmas.

Separado de las rutas porque lo usan dos flujos: firmar una solicitud y firmar
varias en lote (en el lote el PIN se pide una sola vez, pero las reglas se
aplican solicitud por solicitud).
"""

from services.marcas import listas_habilitadas
from services.pins import (
    MAX_INTENTOS, esta_bloqueado, momento_desbloqueo, registrar_intento, verificar_pin,
)
from services.solicitudes import AUTORIZACIONES_REQUERIDAS, marcas_de


class ErrorAutorizante(Exception):
    """El autorizante no pudo validarse (PIN, bloqueo o alta pendiente)."""

    def __init__(self, mensaje, codigo=403, extra=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.extra = extra or {}


def verificar_autorizante(conn, autorizado_id, pin, solicitud_id=None):
    """Valida identidad del autorizante. Devuelve la fila o lanza ErrorAutorizante.
    Cuenta los intentos fallidos y bloquea al llegar al máximo."""
    autorizado = conn.execute(
        'SELECT * FROM autorizados WHERE id = ? AND activo = 1', (autorizado_id,)).fetchone()
    if not autorizado:
        raise ErrorAutorizante('El autorizado no existe', 404)

    bloqueado, minutos = esta_bloqueado(autorizado['bloqueado_hasta'])
    if bloqueado:
        registrar_intento(conn, autorizado['id'], 'bloqueado', solicitud_id)
        conn.commit()
        raise ErrorAutorizante(
            f'{autorizado["nombre"]} está bloqueado por intentos fallidos. '
            f'Volvé a intentar en {minutos} minuto(s) o pedí un blanqueo.', 423)

    if not autorizado['pin_hash']:
        registrar_intento(conn, autorizado['id'], 'sin_pin', solicitud_id)
        conn.commit()
        raise ErrorAutorizante(
            f'{autorizado["nombre"]} todavía no dio de alta su PIN. '
            f'Pedile a administración un código de alta para poder definirlo.',
            409, {'requiere_alta': True})

    if not verificar_pin(pin, autorizado['pin_hash']):
        intentos = (autorizado['intentos_fallidos'] or 0) + 1
        if intentos >= MAX_INTENTOS:
            conn.execute(
                'UPDATE autorizados SET intentos_fallidos = 0, bloqueado_hasta = ? WHERE id = ?',
                (momento_desbloqueo(), autorizado['id']))
            registrar_intento(conn, autorizado['id'], 'bloqueado', solicitud_id)
            conn.commit()
            raise ErrorAutorizante(
                f'PIN incorrecto. {autorizado["nombre"]} queda bloqueado por intentos fallidos.', 423)
        conn.execute('UPDATE autorizados SET intentos_fallidos = ? WHERE id = ?',
                     (intentos, autorizado['id']))
        registrar_intento(conn, autorizado['id'], 'pin_incorrecto', solicitud_id)
        conn.commit()
        raise ErrorAutorizante(
            f'PIN incorrecto. Te quedan {MAX_INTENTOS - intentos} intento(s) antes del bloqueo.', 403)

    # PIN correcto: se limpia el contador de fallidos.
    conn.execute('UPDATE autorizados SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?',
                 (autorizado['id'],))
    registrar_intento(conn, autorizado['id'], 'ok', solicitud_id)
    return autorizado


def firmar(conn, solicitud, autorizado):
    """Aplica las reglas de ESA solicitud y registra la firma.
    Devuelve (ok, motivo, excedio_tope)."""
    if solicitud['estado'] == 'autorizada':
        return False, 'Ya está autorizada', False

    marcas = marcas_de(solicitud)
    if autorizado['lista'] not in listas_habilitadas(marcas):
        detalle = marcas[0] if len(marcas) == 1 else 'esas marcas (requiere autorizante que las cubra todas)'
        return False, f'{autorizado["nombre"]} no está habilitado para {detalle}', False

    ya = conn.execute(
        'SELECT 1 FROM autorizaciones WHERE solicitud_id = ? AND autorizado_id = ?',
        (solicitud['id'], autorizado['id'])).fetchone()
    if ya:
        return False, f'{autorizado["nombre"]} ya autorizó esta solicitud', False

    tope = autorizado['monto_autorizado']
    excedio = tope is not None and float(solicitud['monto_total'] or 0) > tope

    conn.execute(
        'INSERT INTO autorizaciones (solicitud_id, autorizado_id, excedio_tope, monto_tope) '
        'VALUES (?, ?, ?, ?)', (solicitud['id'], autorizado['id'], 1 if excedio else 0, tope))

    firmas = conn.execute('SELECT COUNT(*) AS n FROM autorizaciones WHERE solicitud_id = ?',
                          (solicitud['id'],)).fetchone()['n']
    # Regla: alcanza UNA firma si el monto no supera el tope de quien firmó (o es sin
    # límite). Si lo supera, queda pendiente hasta una segunda firma de otra persona.
    if firmas >= AUTORIZACIONES_REQUERIDAS or (firmas == 1 and not excedio):
        conn.execute('UPDATE solicitudes SET estado = "autorizada", '
                     'updated_at = datetime("now", "localtime") WHERE id = ?', (solicitud['id'],))

    return True, '', excedio
