"""Mail transaccional de marca para apps de Neostar.

Copiar este archivo a la app y usarlo así:

    from mail_neostar import mail_activo, enviar_mail, mail_layout, boton_html

    enviar_mail(destino, f'Recuperar tu contraseña - {APP_NOMBRE}', texto,
                mail_layout('Recuperá tu contraseña', cuerpo_html))

Todo lo que distingue a una app de otra sale de env vars (APP_NOMBRE, APP_COLOR,
APP_LOGO_*): el esqueleto del mail es siempre el mismo. Ver SKILL.md.

Dos transportes, en este orden: **SMTP** (hoy Gmail) si está configurado, y si no
la **API HTTP de SendGrid**. Sin ninguno de los dos no manda nada y solo loguea,
para poder desarrollar y testear sin cuenta de mail.

Sin dependencias nuevas: `smtplib` y `urllib` son de la stdlib. Bajo el worker
gevent de gunicorn los sockets son cooperativos, así que no bloquean el proceso.
"""
import base64
import html as _html
import logging
import os

log = logging.getLogger(__name__)

# ── Identidad de la app ──────────────────────────────────────────────────────
# APP_NOMBRE es lo primero que ve la persona: el nombre del remitente, el asunto
# y el pie del mail. NUNCA dejarlo en el default en producción.
APP_NOMBRE = (os.environ.get('APP_NOMBRE') or 'Neostar').strip()
# Acento del header y del botón. Cambiarlo SOLO si la app ya tiene un acento
# propio en su UI: dos verdes distintos en el mismo portal se leen como un error.
APP_COLOR = (os.environ.get('APP_COLOR') or '#2DB84B').strip()
# Carpeta de donde se leen los logos (el static/ de la app).
STATIC_DIR = os.environ.get('STATIC_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# ── Remitente ────────────────────────────────────────────────────────────────
MAIL_FROM = (os.environ.get('MAIL_FROM') or 'no-reply@neostar.com.ar').strip()
MAIL_FROM_NOMBRE = (os.environ.get('MAIL_FROM_NOMBRE') or APP_NOMBRE).strip()
MAIL_REPLY_TO = (os.environ.get('MAIL_REPLY_TO') or '').strip()

# ── Transportes ──────────────────────────────────────────────────────────────
SMTP_HOST = (os.environ.get('SMTP_HOST') or '').strip()
SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
SMTP_USER = (os.environ.get('SMTP_USER') or '').strip()
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or ''
SENDGRID_API_KEY = (os.environ.get('SENDGRID_API_KEY') or '').strip()

# ── URL pública ──────────────────────────────────────────────────────────────
# Los links de un mail no se corrigen: ya salieron. Por eso el dominio se puede
# fijar a mano en vez de depender del host del request (que detrás de un proxy
# solo es correcto con TRUST_PROXY=1).
PUBLIC_BASE_URL = (os.environ.get('PUBLIC_BASE_URL') or '').strip().rstrip('/')


def base_url(request=None):
    """Raíz absoluta del sitio para los links de los mails."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    if request is not None:
        return request.url_root.rstrip('/')
    return ''


def smtp_configurado():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def mail_activo():
    """True si hay algún transporte configurado. Gatea la UI del recupero: sin
    esto, la pantalla no puede prometer un mail que no va a salir."""
    return smtp_configurado() or bool(SENDGRID_API_KEY)


def remitente():
    """(email, nombre) del From. Con SMTP el From lo impone el proveedor: Gmail
    reescribe (o rechaza) cualquier From que no sea la cuenta autenticada, así
    que MAIL_FROM se ignora a propósito en vez de fingir que se respeta."""
    return (SMTP_USER if smtp_configurado() else MAIL_FROM), MAIL_FROM_NOMBRE


# ── Logos del header ─────────────────────────────────────────────────────────
# Viajan ADENTRO del mail (adjuntos "inline", referenciados por cid:) y no como
# <img src="https://..."> apuntando a /static: la app puede estar en una red
# interna o sin dominio público, y una URL que el cliente de mail no resuelve
# deja el header vacío. El wordmark es la versión BLANCA porque el header es de
# color y en mail no existen los filtros CSS: hace falta el archivo aparte.
_LOGOS = (
    ('logoRobot', os.environ.get('APP_LOGO_ICONO') or 'logo-robot-header.png'),
    ('logoNeostar', os.environ.get('APP_LOGO_WORDMARK') or 'neostar-logo-blanco.png'),
)
_logos_cache = None


def logos_mail():
    """Los logos listos para adjuntar. Se leen y codifican UNA sola vez. Si falta
    un archivo se saltea: el mail sale igual y el header cae al texto del alt."""
    global _logos_cache
    if _logos_cache is None:
        adjuntos = []
        for cid, nombre in _LOGOS:
            ruta = os.path.join(STATIC_DIR, nombre)
            try:
                with open(ruta, 'rb') as f:
                    adjuntos.append({
                        "content": base64.b64encode(f.read()).decode('ascii'),
                        "filename": nombre,
                        "type": "image/png",
                        "disposition": "inline",
                        "content_id": cid,
                    })
            except OSError:
                log.warning("Falta el logo %s para el header de los mails", ruta)
        _logos_cache = adjuntos
    return _logos_cache


# ── Layout de marca ──────────────────────────────────────────────────────────
def mail_layout(titulo, cuerpo_html, app_nombre=None, color=None):
    """Envoltorio de marca de los mails HTML.

    Todo con <table> y estilos inline: los clientes de mail (sobre todo Outlook)
    ignoran <style> y el CSS moderno. El HTML que devuelve referencia los logos
    por `cid:`; de adjuntarlos se encarga `enviar_mail()`, que los engancha solo
    al ver el `cid:`. Si el lector bloquea imágenes (muchos lo hacen por
    default), el `alt` deja el nombre de la marca en el header igual.

    Lo único que cambia entre apps es `app_nombre` y `color`: la estructura, los
    radios y la tipografía son las mismas en todas.

    DIVERGENCIA con el asset de la skill neostar-skill-mail: a la tarjeta se le
    agregaron `align="center"` y `margin:0 auto`. Con el `align` del <td> solo,
    Gmail la dejaba pegada a un costado en ventanas anchas. Si se re-sincroniza
    el asset desde la skill, hay que volver a aplicarlo (y conviene subirlo allá,
    junto con la versión Node, que tiene el mismo HTML).
    """
    app_nombre = app_nombre or APP_NOMBRE
    color = color or APP_COLOR
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0; padding:0; background:#f8fafc;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc; padding:24px 12px;">
 <tr><td align="center">
  <table role="presentation" width="600" align="center" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; margin:0 auto; background:#ffffff; border:1px solid #e5e7eb; border-radius:16px; overflow:hidden; font-family:'Inter',-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">
   <tr><td style="background:{color}; padding:22px 32px;">
     <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
       <td style="padding-right:14px; vertical-align:middle; line-height:0;">
         <img src="cid:logoRobot" width="40" height="39" alt="" style="display:block; border:0;">
       </td>
       <td style="vertical-align:middle; line-height:0;">
         <img src="cid:logoNeostar" width="130" height="38" alt="Neostar" style="display:block; border:0; color:#ffffff; font-size:20px; font-weight:700; line-height:38px;">
       </td>
     </tr></table>
   </td></tr>
   <tr><td style="padding:32px;">
     <h1 style="margin:0 0 16px; font-size:22px; font-weight:700; color:#111827;">{_html.escape(titulo)}</h1>
     {cuerpo_html}
   </td></tr>
   <tr><td style="background:#f8fafc; border-top:1px solid #e5e7eb; padding:20px 32px; font-size:12px; color:#6b7280; line-height:1.6;">
     Mail automático de <strong style="color:#111827;">{_html.escape(app_nombre)}</strong>
   </td></tr>
  </table>
 </td></tr>
</table>
</body></html>"""


def boton_html(texto, link, color=None):
    """CTA del mail + el link en texto. El texto no es redundante: hay clientes
    que no renderizan el botón, y ahí el link pegable es lo único que queda."""
    color = color or APP_COLOR
    return f"""
     <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
       <tr><td style="border-radius:8px; background:{color};">
         <a href="{_html.escape(link, quote=True)}" style="display:inline-block; padding:14px 28px; font-size:15px; font-weight:600; color:#ffffff; text-decoration:none; border-radius:8px;">{_html.escape(texto)}</a>
       </td></tr>
     </table>
     <p style="margin:0 0 24px; font-size:13px; color:#6b7280; line-height:1.6;">
       El link vence en <strong style="color:#111827;">30 minutos</strong> y se puede usar una sola vez.
       Si el botón no funciona, copiá y pegá esta dirección en tu navegador:<br>
       <span style="color:{color}; word-break:break-all;">{_html.escape(link)}</span>
     </p>"""


# ── Envío ────────────────────────────────────────────────────────────────────
def _enviar_por_smtp(to_email, subject, text_body, html_body=None, imagenes_inline=None):
    import smtplib
    from email.message import EmailMessage
    from email.utils import formataddr

    desde, nombre = remitente()
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = formataddr((nombre, desde))
    msg['To'] = to_email
    if MAIL_REPLY_TO:
        msg['Reply-To'] = MAIL_REPLY_TO
    # El plano primero y el HTML como alternativa. No es decorativo: es lo que
    # lee quien tiene el HTML desactivado, y suma antispam.
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype='html')
        if imagenes_inline:
            # Los logos van "related" a la parte HTML (no como adjuntos sueltos):
            # así el lector los resuelve por cid: y no los muestra como archivos.
            parte_html = msg.get_payload()[-1]
            for img in imagenes_inline:
                # Sin `filename` a propósito: con nombre de archivo, algunos
                # clientes (Apple Mail) los listan como adjuntos para bajar.
                parte_html.add_related(
                    base64.b64decode(img['content']),
                    maintype='image', subtype='png',
                    cid=f"<{img['content_id']}>",
                    disposition='inline',
                )
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    return True


def enviar_mail(to_email, subject, text_body, html_body=None, imagenes_inline=None):
    """Manda un mail transaccional. Devuelve True/False y **nunca lanza**: un mail
    que no salió no puede tumbar el request que lo dispara."""
    if html_body and imagenes_inline is None and 'cid:' in html_body:
        # Un HTML que referencia `cid:` SIN esas partes adjuntas llega con las
        # imágenes rotas. Se enganchan acá y no en cada llamador justamente
        # porque olvidarse es fácil. Para HTML de marca sin logos: imagenes_inline=[].
        imagenes_inline = logos_mail()

    if smtp_configurado():
        try:
            return _enviar_por_smtp(to_email, subject, text_body, html_body, imagenes_inline)
        except Exception:
            log.warning("No se pudo mandar el mail (SMTP) a %s", to_email, exc_info=True)
            return False

    if not SENDGRID_API_KEY:
        log.info("[mail no enviado, sin transporte configurado] to=%s subject=%r", to_email, subject)
        return False

    import json as _json
    import urllib.request
    # El orden importa: SendGrid exige text/plain ANTES que text/html.
    content = [{"type": "text/plain", "value": text_body}]
    if html_body:
        content.append({"type": "text/html", "value": html_body})
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": MAIL_FROM, "name": MAIL_FROM_NOMBRE},
        "subject": subject,
        "content": content,
    }
    if MAIL_REPLY_TO:
        payload["reply_to"] = {"email": MAIL_REPLY_TO}
    if imagenes_inline:
        payload["attachments"] = list(imagenes_inline)
    req = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=_json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {SENDGRID_API_KEY}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return 200 <= resp.status < 300
    except Exception:
        log.warning("No se pudo mandar el mail a %s", to_email, exc_info=True)
        return False
