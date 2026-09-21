"""Avisos por mail del circuito de autorizacion.

Dos momentos, dos destinatarios:

1. **Alta del gasto** -> a los autorizantes de esa marca: hay una AGC esperando
   firma. Sin esa firma el gasto no avanza; ese es todo el motivo del mail.
2. **Queda autorizada** -> a la cajera de cada razon social imputada: ya puede
   pagarse.

Reglas (aprendidas del Cotizador de Subastas, no son negociables):

- El aviso sale DESPUES de persistir, nunca antes.
- Es best-effort: `enviar_mail()` nunca lanza y el llamador ademas envuelve en
  try/except. Un SMTP caido no puede voltear la carga del gasto.
- Un mail por destinatario, nunca un `To:` con todos: no se ven las casillas
  entre si y un rebote no se lleva puesto al otro aviso.
- Los destinatarios salen de env vars. Los defaults de abajo son los vigentes;
  mover a alguien es tocar el `.env`, no el codigo. Lista vacia = no se avisa.
- El link sale de `base_url()` (PUBLIC_BASE_URL), no de `request.url_root`
  pelado: detras de nginx el request dice `backend:5000` y el mail ya salio.
- Sale una sola vez por transicion, marcada en la base (ver `_marcar`).
"""

import html
import logging
import os

from mail_neostar import APP_COLOR, APP_NOMBRE, base_url, enviar_mail, mail_layout
from models.database import get_db
from services.marcas import CONCEPTOS, listas_habilitadas
from services.pdf_fill import fmt_money
from services.solicitudes import marcas_de

log = logging.getLogger(__name__)

# Ruta de la pantalla donde se firma: el mail lleva al detalle de la solicitud,
# no al home. Ahi el autorizante elige su nombre y confirma con su PIN.
RUTA_DETALLE = '/proceso-compra/solicitudes/{id}'

# Autorizantes por planilla. La planilla (no la marca) es lo que decide quien
# puede firmar: ver services/marcas.py. Con varias marcas tildadas solo quedan
# habilitados los de Multimarca, y el aviso los sigue: le escribe a quien
# realmente puede firmar ese gasto.
_AUTORIZANTES = {
    'nissan': 'mscerra@neostar.com.ar,iparolin@neostar.com.ar,'
              'wpalomino@neostar.com.ar,iaguilar@neostar.com.ar',
    'jeep': 'afernandez@neostar.com.ar,isiffredi@neostar.com.ar,'
            'ldiscipio@neostar.com.ar,mcalvete@neostar.com.ar',
    'jeep_byd': 'lcaceres@neostar.com.ar',
    'kia': 'botero@neostar.com.ar,cbourquin@neostar.com.ar,'
           'lromero@neostar.com.ar,mcolombera@neostar.com.ar',
    'honda': 'gbru@neostar.com.ar,mgonzalez@neostar.com.ar',
    'byd': 'lharik@neostar.com.ar',
    'multimarca': 'lfalletti@neostar.com.ar,jazzolini@neostar.com.ar,'
                  'dubiergo@neostar.com.ar,cgiorgetti@alcorosario.com.ar,'
                  'storres@neostar.com.ar,vlottero@neostar.com.ar',
}

# Cajeras de administracion, por razon social a la que se imputa el pago.
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
    """A quien hay que avisarle que este gasto espera firma."""
    destinos = []
    for lista in listas_habilitadas(marcas_de(solicitud)):
        destinos += _lista(_config(f'AVISO_{lista.upper()}', _AUTORIZANTES.get(lista, '')))
    # Copia fija para administracion/compras, ademas de los de la marca.
    destinos += _lista(_config('AUTORIZA_NOTIF_EMAIL'))
    return _lista(','.join(destinos))


def destinatarios_cajeras(solicitud):
    """La cajera de cada razon social a la que se imputa el gasto."""
    destinos = []
    for empresa in (solicitud.get('empresas') or []):
        clave = _clave_empresa(empresa)
        destinos += _lista(_config(f'CAJA_{clave}', _CAJERAS.get(clave, '')))
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


def _boton(texto, link):
    """CTA del mail + el link en texto (hay clientes que no renderizan el boton,
    y ahi el link pegable es lo unico que queda).

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
       Se firma dentro de la app, con tu PIN. Si el boton no funciona, copia y pega
       esta direccion en tu navegador:<br>
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
        ('Monto', f'$ {fmt_money(solicitud.get("monto_total"))}'),
        ('Empresa', ', '.join(solicitud.get('empresas') or [])),
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
    """Avisa a los autorizantes que hay un gasto nuevo esperando su firma.

    Se llama DESPUES de guardar el gasto, y una sola vez: en la transicion a
    pendiente (el alta). Editar un gasto ya cargado no vuelve a avisar.
    """
    if not _marcar(solicitud['id'], 'notificado_at'):
        return 0

    destinos = destinatarios_autorizantes(solicitud)
    if not destinos:
        log.info('Solicitud #%s sin destinatarios de aviso configurados', solicitud['id'])
        return 0

    link = _link(solicitud['id'], request)
    proveedor = solicitud.get('proveedor_nombre') or 'sin proveedor'
    monto = fmt_money(solicitud.get('monto_total'))
    resumen_txt, resumen_html = _resumen(solicitud)

    texto = (
        f'Se cargo un gasto que necesita autorizacion.\n\n'
        f'{resumen_txt}\n\n'
        f'La solicitud queda PENDIENTE: no avanza hasta que un autorizante la firme.\n\n'
        f'Para autorizarla, entra a la app y confirma con tu PIN:\n{link}\n\n'
        f'--\nMail automatico de {APP_NOMBRE}'
    )
    cuerpo = (
        '<p style="margin:0 0 16px; font-size:15px; color:#111827; line-height:1.6;">'
        f'{html.escape(solicitud.get("solicitado_por") or "Un colaborador")} cargo un gasto '
        'que necesita tu autorizacion.</p>'
        + resumen_html
        + '<p style="margin:0 0 24px; padding:14px 16px; background:#fff7ed; '
          'border-left:3px solid #f59e0b; border-radius:8px; font-size:14px; '
          'color:#111827; line-height:1.6;">La solicitud queda <strong>pendiente</strong> '
          'y no avanza hasta que alguien la autorice.</p>'
        + _boton('Ver y autorizar', link)
    )
    return _enviar_a_cada_uno(
        destinos, f'Gasto para autorizar: {proveedor} - $ {monto}',
        texto, mail_layout('Gasto para autorizar', cuerpo), 'gasto a autorizar')


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
    monto = fmt_money(solicitud.get('monto_total'))
    resumen_txt, resumen_html = _resumen(solicitud)
    firmantes = ', '.join(a['nombre'] for a in (solicitud.get('autorizaciones') or []))

    texto = (
        f'La solicitud #{solicitud["id"]} quedo AUTORIZADA.\n\n'
        f'{resumen_txt}\n'
        + (f'Autorizo: {firmantes}\n' if firmantes else '')
        + f'\nYa se puede gestionar el pago. La autorizacion, la factura y el ZIP '
          f'estan en la app:\n{link}\n\n'
          f'--\nMail automatico de {APP_NOMBRE}'
    )
    cuerpo = (
        '<p style="margin:0 0 16px; font-size:15px; color:#111827; line-height:1.6;">'
        f'La solicitud <strong>#{solicitud["id"]}</strong> quedo '
        '<strong>autorizada</strong>: ya se puede gestionar el pago.</p>'
        + resumen_html
        + (f'<p style="margin:0 0 24px; font-size:14px; color:#111827;">Autorizo: '
           f'<strong>{html.escape(firmantes)}</strong></p>' if firmantes else '')
        + _boton('Ver la autorizacion', link)
    )
    return _enviar_a_cada_uno(
        destinos, f'Factura autorizada: {proveedor} - $ {monto}',
        texto, mail_layout('Factura autorizada', cuerpo), 'factura autorizada')
