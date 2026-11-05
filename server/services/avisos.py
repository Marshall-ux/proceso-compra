"""Avisos por mail del circuito de autorizacion.

Dos momentos, dos destinatarios:

1. **Alta del gasto** -> exclusivamente al firmante que eligio quien cargo la
   solicitud (uno solo, de entre los que pueden firmarlo por marca y monto): hay
   una AGC esperando su firma. Sin copia a nadie mas.
2. **Queda autorizada** -> a la cajera de cada razon social imputada, segun la
   ubicacion (Rosario / Santa Fe) de la solicitud: ya puede pagarse.

Reglas (aprendidas del Cotizador de Subastas, no son negociables):

- El aviso sale DESPUES de persistir, nunca antes.
- Es best-effort: `enviar_mail()` nunca lanza y el llamador ademas envuelve en
  try/except. Un SMTP caido no puede voltear la carga del gasto.
- Un mail por destinatario, nunca un `To:` con todos: no se ven las casillas
  entre si y un rebote no se lleva puesto al otro aviso.
- El mail de cada autorizante esta en la base (lo mantiene administracion desde
  el panel). Las cajeras salen de env vars, con los defaults de abajo; mover a
  alguien es tocar el `.env`. Lista vacia = no se avisa.
- El link sale de `base_url()` (PUBLIC_BASE_URL), no de `request.url_root`
  pelado: detras de nginx el request dice `backend:5000` y el mail ya salio.
- Sale una sola vez por transicion, marcada en la base (ver `_marcar`).
"""

import html
import logging
import os

from mail_neostar import APP_COLOR, APP_NOMBRE, base_url, enviar_mail, mail_layout
from models.database import get_db
from services.marcas import CONCEPTOS, UBICACIONES
from services.pdf_fill import fmt_equivalente, fmt_importe
from services.solicitudes import ids_avisar_a, marcas_de

log = logging.getLogger(__name__)

# Ruta de la pantalla donde se firma: el mail lleva al detalle de la solicitud,
# no al home. Ahi el autorizante elige su nombre y confirma con su PIN.
RUTA_DETALLE = '/proceso-compra/solicitudes/{id}'

# Cajeras de administracion, por ubicacion de la solicitud y razon social a la que
# se imputa el pago (listado pasado por administracion el 05-11-2026).
# Env var para pisar cada una: CAJA_<UBICACION>_<EMPRESA>, ej. CAJA_SANTA_FE_HIKARI.
_CAJERAS_POR_UBICACION = {
    ('ROSARIO', 'ALCO_ROSARIO'): 'nblois@neostar.com.ar',
    ('SANTA_FE', 'ALCO_ROSARIO'): 'mgonzalez@neostar.com.ar',
    ('ROSARIO', 'NEOSTAR'): 'mspurello@neostar.com.ar',
    ('SANTA_FE', 'NEOSTAR'): 'evanlesberg@neostar.com.ar',
    ('ROSARIO', 'HIKARI'): 'bcoll@neostar.com.ar',
    ('SANTA_FE', 'HIKARI'): 'dmorelli@neostar.com.ar',
}

# Cajera por razon social sola: es la que se usaba antes de que existiera la
# ubicacion. Sirve para las solicitudes viejas (sin ubicacion) y para las razones
# sociales que el listado por sede no cubre (XINOXIA, DASEOS).
# Env var: CAJA_<EMPRESA>.
_CAJERAS = {
    'ALCO_ROSARIO': 'nblois@neostar.com.ar',
    'NEOSTAR': 'mspurello@neostar.com.ar',
    'XINOXIA': 'mlhenning@neostar.com.ar',
    'DASEOS': 'mspurello@neostar.com.ar',
    'HIKARI': 'bcoll@neostar.com.ar',
}


def _lista(crudo):
    """Parsea 'a@x, b@x' -> ['a@x', 'b@x']. Filtra vacios y lo que no sea un
    mail, y saca duplicados conservando el orden: la misma persona puede estar
    en dos planillas (Multimarca cubre todas) y no tiene que recibir dos mails."""
    vistos, salida = set(), []
    for parte in str(crudo or '').replace(';', ',').split(','):
        mail = parte.strip()
        clave = mail.lower()
        if '@' in mail and clave not in vistos:
            vistos.add(clave)
            salida.append(mail)
    return salida


def _config(variable, default=''):
    """Valor de una env var, con el default del codigo. La env var puede estar
    definida y vacia a proposito: eso significa 'no avisar a nadie'."""
    valor = os.environ.get(variable)
    return default if valor is None else valor


def _clave_empresa(empresa):
    """'ALCO ROSARIO S.A.' -> 'ALCO_ROSARIO' (el sufijo de la razon social no
    distingue nada y complica el nombre de la env var)."""
    texto = str(empresa or '').upper()
    for sufijo in (' S.A.', ' SA', ' S.A', ' S.R.L.', ' SRL'):
        if texto.endswith(sufijo):
            texto = texto[: -len(sufijo)]
            break
    return '_'.join(''.join(c if c.isalnum() else ' ' for c in texto).split())


def destinatarios_autorizantes(solicitud):
    """A quien hay que avisarle que este gasto espera firma: exclusivamente el
    firmante que eligio quien cargo la solicitud.

    Sin copia fija ni fallback a "toda la planilla": elegir es obligatorio en el
    alta, y el pedido es que el mail le llegue solo a la persona elegida."""
    ids = ids_avisar_a(solicitud)
    if not ids:
        return []
    conn = get_db()
    try:
        destinos = [r['email'] for r in conn.execute(
            f'SELECT email FROM autorizados WHERE id IN ({", ".join("?" * len(ids))})', ids)]
    finally:
        conn.close()
    return _lista(','.join(destinos))


def _cajera(ubicacion, empresa):
    """Mail(s) de la cajera de una razon social en una ubicacion. Primero el listado
    por sede (env var y despues default); si la solicitud no tiene ubicacion o la
    razon social no esta en ese listado, la cajera por razon social de siempre."""
    clave = _clave_empresa(empresa)
    sede = _clave_empresa(ubicacion)
    if sede:
        especifica = _config(f'CAJA_{sede}_{clave}',
                             _CAJERAS_POR_UBICACION.get((sede, clave)))
        if especifica is not None:
            return _lista(especifica)
    return _lista(_config(f'CAJA_{clave}', _CAJERAS.get(clave, '')))


def destinatarios_cajeras(solicitud):
    """La cajera de cada razon social a la que se imputa el gasto, en la ubicacion
    de la solicitud."""
    destinos = []
    for empresa in (solicitud.get('empresas') or []):
        destinos += _cajera(solicitud.get('ubicacion'), empresa)
    return _lista(','.join(destinos))


def _marcar(solicitud_id, campo):
    """Marca la transicion como avisada y dice si le toco a esta llamada hacerlo.

    Es lo que hace que el aviso salga UNA vez: el UPDATE solo pega si la marca
    estaba vacia, asi que dos llamadas en paralelo (o una edicion posterior del
    gasto) no repiten el mail. Se marca ANTES de enviar: ante la duda preferimos
    no duplicar el aviso antes que reintentarlo, y el fallo queda en el log."""
    assert campo in ('notificado_at', 'cajeras_notificado_at')
    conn = get_db()
    try:
        cur = conn.execute(
            f"UPDATE solicitudes SET {campo} = datetime('now', 'localtime') "
            f"WHERE id = ? AND ({campo} IS NULL OR {campo} = '')", (solicitud_id,))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def _link(solicitud_id, request=None):
    return base_url(request) + RUTA_DETALLE.format(id=solicitud_id)


def _asunto(texto):
    """Un asunto con saltos de linea llega roto o rebota: se aplasta a una linea."""
    return ' '.join(str(texto or '').split())


def _boton(texto, link, nota=''):
    """CTA del mail + el link en texto (hay clientes que no renderizan el boton,
    y ahi el link pegable es lo unico que queda).

    `nota` es la aclaracion previa al link, y cambia segun a quien le escribimos:
    lo del PIN solo tiene sentido para quien va a firmar. A la cajera el link le
    sirve para mirar y descargar, no para autorizar nada.

    No se usa `boton_html()` de mail_neostar porque su pie dice que el link vence
    en 30 minutos y es de un solo uso: eso vale para el recupero de contrasena,
    no para este link, que es la pantalla de siempre y no es una credencial.
    """
    return f"""
     <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
       <tr><td style="border-radius:8px; background:{APP_COLOR};">
         <a href="{html.escape(link, quote=True)}" style="display:inline-block; padding:14px 28px; font-size:15px; font-weight:600; color:#ffffff; text-decoration:none; border-radius:8px;">{html.escape(texto)}</a>
       </td></tr>
     </table>
     <p style="margin:0 0 24px; font-size:13px; color:#6b7280; line-height:1.6;">
       {nota}Si el botón no funciona, copiá y pegá esta dirección en tu navegador:<br>
       <span style="color:{APP_COLOR}; word-break:break-all;">{html.escape(link)}</span>
     </p>"""


def _dato(etiqueta, valor):
    """Fila de la tabla de datos del mail. Escapa el valor: lo escribio el
    colaborador (proveedor, descripcion, observaciones)."""
    if not str(valor or '').strip():
        return ''
    return (f'<tr><td style="padding:4px 16px 4px 0; font-size:13px; color:#6b7280; '
            f'white-space:nowrap; vertical-align:top;">{html.escape(str(etiqueta))}</td>'
            f'<td style="padding:4px 0; font-size:14px; color:#111827;">'
            f'{html.escape(str(valor))}</td></tr>')


def _resumen(solicitud):
    """(texto plano, tabla HTML) con los datos que hacen falta para decidir."""
    filas = [
        ('Solicitud', f'#{solicitud["id"]}'),
        ('Proveedor', solicitud.get('proveedor_nombre')),
        ('CUIT', solicitud.get('cuit')),
        ('Monto', fmt_importe(solicitud.get('monto_total'), solicitud.get('moneda'))
         + (f' ({fmt_equivalente(solicitud)})' if fmt_equivalente(solicitud) else '')),
        ('Empresa', ', '.join(solicitud.get('empresas') or [])),
        ('Ubicación', UBICACIONES.get(solicitud.get('ubicacion'), solicitud.get('ubicacion'))),
        ('Marca', ', '.join(marcas_de(solicitud))),
        ('Concepto', solicitud.get('concepto_otro')
         or CONCEPTOS.get(solicitud.get('concepto'), solicitud.get('concepto'))),
        ('Criticidad', solicitud.get('criticidad_obs') or solicitud.get('criticidad')),
        ('Solicita', solicitud.get('solicitado_por')),
        ('Observaciones', solicitud.get('observaciones')),
    ]
    texto = '\n'.join(f'{k}: {v}' for k, v in filas if str(v or '').strip())
    tabla = ('<table role="presentation" cellpadding="0" cellspacing="0" '
             'style="margin:0 0 24px; width:100%;">'
             + ''.join(_dato(k, v) for k, v in filas) + '</table>')
    return texto, tabla


def _enviar_a_cada_uno(destinos, asunto, texto, html_body, motivo):
    """Un mail por destinatario. Devuelve cuantos salieron."""
    asunto = _asunto(asunto)
    enviados = 0
    for destino in destinos:
        if enviar_mail(destino, asunto, texto, html_body):
            enviados += 1
        else:
            log.warning('No salio el aviso de %s a %s', motivo, destino)
    log.info('Aviso de %s: %s de %s destinatarios', motivo, enviados, len(destinos))
    return enviados


def notificar_gasto_a_autorizar(solicitud, request=None):
    """Avisa al firmante elegido que hay un gasto nuevo esperando su firma.

    Se llama DESPUES de guardar el gasto, y una sola vez: en la transicion a
    pendiente (el alta). Editar un gasto ya cargado no vuelve a avisar, salvo que
    se cambie el firmante (ver `notificar_cambio_firmante`).
    """
    if not _marcar(solicitud['id'], 'notificado_at'):
        return 0
    return _mail_para_firmar(solicitud, request)


def notificar_cambio_firmante(solicitud, request=None):
    """Avisa al firmante nuevo cuando se edita la solicitud y se elige a otro. Sin
    marca de idempotencia: lo dispara solo la edicion que cambia el firmante, y
    cada cambio es un firmante distinto que tiene que enterarse."""
    if solicitud.get('estado') != 'pendiente':
        return 0
    return _mail_para_firmar(solicitud, request)


def notificar_corregida(solicitud, request=None):
    """Avisa al firmante que corrigieron la solicitud que había devuelto: vuelve a
    estar pendiente de su firma. Lo dispara la edición de una solicitud observada."""
    if solicitud.get('estado') != 'pendiente':
        return 0
    return _mail_para_firmar(solicitud, request, corregida=True)


def _mail_para_firmar(solicitud, request=None, corregida=False):
    destinos = destinatarios_autorizantes(solicitud)
    if not destinos:
        log.info('Solicitud #%s sin destinatarios de aviso configurados', solicitud['id'])
        return 0

    link = _link(solicitud['id'], request)
    proveedor = solicitud.get('proveedor_nombre') or 'sin proveedor'
    monto = fmt_importe(solicitud.get('monto_total'), solicitud.get('moneda'))
    resumen_txt, resumen_html = _resumen(solicitud)

    if corregida:
        apertura_txt = f'Corrigieron la solicitud #{solicitud["id"]} que habías devuelto para corregir.'
        apertura_html = (f'Corrigieron la solicitud <strong>#{solicitud["id"]}</strong> que '
                         'habías devuelto para corregir: ya la podés revisar de nuevo.')
        asunto = f'Corregida, para autorizar: {proveedor} - {monto}'
    else:
        apertura_txt = 'Se cargó un gasto que necesita autorización.'
        apertura_html = (f'{html.escape(solicitud.get("solicitado_por") or "Un colaborador")} '
                         'cargó un gasto que necesita tu autorización.')
        asunto = f'Gasto para autorizar: {proveedor} - {monto}'

    texto = (
        f'{apertura_txt}\n\n'
        f'{resumen_txt}\n\n'
        f'Te eligieron como firmante: sos la única persona que puede autorizarla, '
        f'y la solicitud queda PENDIENTE hasta que la firmes.\n\n'
        f'Para autorizarla, entrá a la app y confirmá con tu PIN:\n{link}\n\n'
        f'--\nMail automático de {APP_NOMBRE}'
    )
    cuerpo = (
        '<p style="margin:0 0 16px; font-size:15px; color:#111827; line-height:1.6;">'
        f'{apertura_html}</p>'
        + resumen_html
        + '<p style="margin:0 0 24px; padding:14px 16px; background:#fff7ed; '
          'border-left:3px solid #f59e0b; border-radius:8px; font-size:14px; '
          'color:#111827; line-height:1.6;">Te eligieron como firmante: sos la '
          '<strong>única persona</strong> que puede autorizarla, y queda '
          '<strong>pendiente</strong> hasta que la firmes.</p>'
        + _boton('Ver y autorizar', link, 'Se firma dentro de la app, con tu PIN. ')
    )
    return _enviar_a_cada_uno(
        destinos, asunto, texto, mail_layout('Gasto para autorizar', cuerpo), 'gasto a autorizar')


def notificar_recordatorio(autorizado, pendientes, request=None):
    """Recordatorio a un firmante de las solicitudes que siguen esperando su firma
    (ver services/recordatorios.py). Un solo mail con todas las que le vencieron.
    `pendientes` es una lista de (solicitud, número de recordatorio: 1 o 2)."""
    destinos = _lista(autorizado['email'])
    if not destinos:
        log.info('Recordatorio de firma sin mail para %s', autorizado['nombre'])
        return 0

    filas_txt, filas_html = [], []
    for s, numero in pendientes:
        monto = fmt_importe(s.get('monto_total'), s.get('moneda'))
        espera = 'hace más de una semana' if numero == 2 else 'hace más de 48 h'
        link = _link(s['id'], request)
        proveedor = s.get('proveedor_nombre') or 'sin proveedor'
        filas_txt.append(f'- #{s["id"]} {proveedor}, {monto} (espera {espera}): {link}')
        filas_html.append(
            '<tr><td style="padding:6px 12px 6px 0; font-size:14px;">'
            f'<a href="{html.escape(link, quote=True)}" style="color:{APP_COLOR}; font-weight:600;">'
            f'#{s["id"]}</a></td>'
            f'<td style="padding:6px 12px 6px 0; font-size:14px; color:#111827;">{html.escape(proveedor)}</td>'
            f'<td style="padding:6px 12px 6px 0; font-size:14px; white-space:nowrap;">{html.escape(monto)}</td>'
            f'<td style="padding:6px 0; font-size:13px; color:#6b7280;">espera {espera}</td></tr>')

    n = len(pendientes)
    asunto = (f'Recordatorio: {n} solicitudes esperan tu firma' if n > 1
              else f'Recordatorio: la solicitud #{pendientes[0][0]["id"]} espera tu firma')
    inicio = base_url(request) + '/proceso-compra/'
    texto = (
        f'{"Estas solicitudes siguen" if n > 1 else "Esta solicitud sigue"} esperando tu firma:\n\n'
        + '\n'.join(filas_txt)
        + f'\n\nSe firman en la app, con tu PIN. En el inicio, "Para firmar" las tiene todas:\n{inicio}\n\n'
          f'--\nMail automático de {APP_NOMBRE}'
    )
    cuerpo = (
        '<p style="margin:0 0 16px; font-size:15px; color:#111827; line-height:1.6;">'
        f'{"Estas solicitudes siguen" if n > 1 else "Esta solicitud sigue"} esperando tu firma. '
        'Hasta que la firmes, el gasto no avanza.</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px; width:100%;">'
        + ''.join(filas_html) + '</table>'
        + _boton('Ir a "Para firmar"', inicio, 'Se firma dentro de la app, con tu PIN. ')
    )
    return _enviar_a_cada_uno(destinos, asunto, texto,
                              mail_layout('Recordatorio de firma', cuerpo), 'recordatorio de firma')


def notificar_autorizada(solicitud, request=None):
    """Avisa a las cajeras de cada razon social que la factura ya esta autorizada.

    Se llama despues de registrar la firma que completa la autorizacion, y una
    sola vez por solicitud.
    """
    if solicitud.get('estado') != 'autorizada':
        return 0
    if not _marcar(solicitud['id'], 'cajeras_notificado_at'):
        return 0

    destinos = destinatarios_cajeras(solicitud)
    if not destinos:
        log.info('Solicitud #%s autorizada sin cajeras configuradas para %s',
                 solicitud['id'], solicitud.get('empresas'))
        return 0

    link = _link(solicitud['id'], request)
    proveedor = solicitud.get('proveedor_nombre') or 'sin proveedor'
    monto = fmt_importe(solicitud.get('monto_total'), solicitud.get('moneda'))
    resumen_txt, resumen_html = _resumen(solicitud)
    firmantes = ', '.join(a['nombre'] for a in (solicitud.get('autorizaciones') or []))

    texto = (
        f'La solicitud #{solicitud["id"]} quedó AUTORIZADA.\n\n'
        f'{resumen_txt}\n'
        + (f'Autorizó: {firmantes}\n' if firmantes else '')
        + f'\nYa se puede gestionar el pago. La autorización, la factura y el ZIP '
          f'están en la app:\n{link}\n\n'
          f'--\nMail automático de {APP_NOMBRE}'
    )
    cuerpo = (
        '<p style="margin:0 0 16px; font-size:15px; color:#111827; line-height:1.6;">'
        f'La solicitud <strong>#{solicitud["id"]}</strong> quedó '
        '<strong>autorizada</strong>: ya se puede gestionar el pago.</p>'
        + resumen_html
        + (f'<p style="margin:0 0 24px; font-size:14px; color:#111827;">Autorizó: '
           f'<strong>{html.escape(firmantes)}</strong></p>' if firmantes else '')
        # Sin la nota del PIN: la cajera no firma, entra a ver y a descargar.
        + _boton('Ver la autorización', link)
    )
    return _enviar_a_cada_uno(
        destinos, f'Factura autorizada: {proveedor} - {monto}',
        texto, mail_layout('Factura autorizada', cuerpo), 'factura autorizada')
