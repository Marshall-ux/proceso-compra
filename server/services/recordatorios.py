"""Recordatorios al firmante de las solicitudes que siguen esperando su firma.

Regla (decidida el 5-11-2026): después del mail del alta, un recordatorio a las 48 h
y otro una semana después de ese. Ahí se corta: tres mails como máximo. Solo en días
hábiles de 8 a 18 (hora de Argentina): si el plazo se cumple de noche o un fin de
semana, sale en el próximo horario hábil. Los feriados no se contemplan.

- Cuenta desde que le toca firmar a la persona actual: el alta, o la última vez que
  se cambió el firmante o se corrigió una devuelta (`aviso_firmante_at`).
- Solo pendientes con firmante elegido que todavía puede firmarla (activo, habilitado
  para la marca, con tope suficiente): no se le recuerda a nadie algo que no puede
  firmar. Las viejas sin firmante no tienen a quién recordarle.
- Si a una persona le vencen varias en la misma pasada, recibe un solo mail con todas.
- Cada recordatorio se marca antes de mandarlo, como los demás avisos: ante la duda
  no se duplica (si el mail falla, queda en el log).

Lo corre un hilo de la app cada 15 minutos (`iniciar`), así no hace falta un cron.
"""

import logging
import threading
import time
from datetime import datetime, timedelta

from models.database import get_db
from services import avisos
from services.marcas import listas_habilitadas
from services.solicitudes import ids_avisar_a, marcas_de, monto_pesos

log = logging.getLogger(__name__)

PRIMERO = timedelta(hours=48)
SEGUNDO = timedelta(days=7)
HORA_DESDE, HORA_HASTA = 8, 18
INTERVALO_SEGUNDOS = 15 * 60
_FORMATO = '%Y-%m-%d %H:%M:%S'


def en_horario(ahora):
    """Días hábiles (lunes a viernes) de 8 a 18."""
    return ahora.weekday() < 5 and HORA_DESDE <= ahora.hour < HORA_HASTA


def _fecha(valor):
    try:
        return datetime.strptime(str(valor)[:19], _FORMATO)
    except (TypeError, ValueError):
        return None


def _puede_firmar(autorizado, solicitud):
    """El elegido sigue pudiendo firmarla: activo, habilitado para la marca y con tope."""
    if not autorizado or not autorizado['activo']:
        return False
    if autorizado['lista'] not in listas_habilitadas(marcas_de(solicitud)):
        return False
    tope = autorizado['monto_autorizado']
    return tope is None or monto_pesos(solicitud) <= tope


def _que_toca(solicitud, ahora):
    """Qué recordatorio le toca: 'recordatorio1_at', 'recordatorio2_at' o None."""
    if not solicitud['recordatorio1_at']:
        desde = _fecha(solicitud['aviso_firmante_at'] or solicitud['created_at'])
        return 'recordatorio1_at' if desde and ahora >= desde + PRIMERO else None
    if not solicitud['recordatorio2_at']:
        primero = _fecha(solicitud['recordatorio1_at'])
        return 'recordatorio2_at' if primero and ahora >= primero + SEGUNDO else None
    return None


def enviar(ahora=None):
    """Manda los recordatorios vencidos. Devuelve cuántos mails salieron."""
    ahora = ahora or datetime.now()
    if not en_horario(ahora):
        return 0
    marca = ahora.strftime(_FORMATO)
    por_firmante = {}   # autorizado_id -> [(solicitud, número de recordatorio)]
    conn = get_db()
    try:
        autorizados = {r['id']: r for r in conn.execute(
            'SELECT id, nombre, email, lista, monto_autorizado, activo FROM autorizados')}
        pendientes = conn.execute(
            "SELECT * FROM solicitudes WHERE estado = 'pendiente' AND recordatorio2_at IS NULL").fetchall()
        for s in pendientes:
            campo = _que_toca(s, ahora)
            if not campo:
                continue
            firmantes = [i for i in ids_avisar_a(s) if _puede_firmar(autorizados.get(i), s)]
            if not firmantes:
                continue
            # Se marca antes de mandar: dos pasadas a la vez no repiten el mail.
            cur = conn.execute(f'UPDATE solicitudes SET {campo} = ? WHERE id = ? AND {campo} IS NULL',
                               (marca, s['id']))
            conn.commit()
            if cur.rowcount != 1:
                continue
            numero = 1 if campo == 'recordatorio1_at' else 2
            for i in firmantes:
                por_firmante.setdefault(i, []).append((dict(s), numero))
    finally:
        conn.close()

    return sum(avisos.notificar_recordatorio(autorizados[i], lista)
               for i, lista in por_firmante.items())


def _bucle():
    time.sleep(60)   # que la app termine de arrancar
    while True:
        try:
            enviar()
        except Exception:
            log.exception('Fallaron los recordatorios de firma')
        time.sleep(INTERVALO_SEGUNDOS)


_iniciado = False


def iniciar():
    """Arranca el hilo que revisa los recordatorios cada 15 minutos (una vez por proceso)."""
    global _iniciado
    if _iniciado:
        return
    _iniciado = True
    threading.Thread(target=_bucle, name='recordatorios', daemon=True).start()
