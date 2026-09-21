"""Prueba el envío de mail de la app contra el proveedor configurado.

Uso (desde la carpeta de la app):

    python probar_mail.py                      # se lo manda a la propia casilla
    python probar_mail.py alguien@dominio.com  # a otro destinatario

Manda un mail REAL usando el mismo `enviar_mail()` que usa la app, no una
implementación paralela: si esto llega, los avisos de autorización también llegan.
Lee la config del `.env` de la raíz del repo (la app en Docker la recibe por el
`environment:` del compose, pero corriendo suelto acá no hay nadie que la
inyecte). No hay dependencias nuevas: el `.env` se parsea a mano.

NUNCA imprime la contraseña: de un diagnóstico no tiene que salir un secreto.
"""
import os
import sys

# La consola de Windows suele venir en cp1252: que un acento no tumbe el test.
try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass


def cargar_env(ruta):
    """Parseo mínimo de un .env: VAR=valor, ignorando comentarios y vacías.
    No pisa lo que ya esté en el entorno real (ese manda)."""
    if not os.path.exists(ruta):
        return 0
    puestas = 0
    with open(ruta, encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#') or '=' not in linea:
                continue
            clave, _, valor = linea.partition('=')
            clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
            if clave and clave not in os.environ:
                os.environ[clave] = valor
                puestas += 1
    return puestas


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cargar_env(os.path.join(raiz, '.env'))

    # Se importa DESPUÉS de cargar el .env: el módulo lee las env vars al importarse.
    import mail_neostar as M

    print('-' * 62)
    print('  Configuración detectada')
    print('-' * 62)
    print(f'  App         : {M.APP_NOMBRE}')
    if M.smtp_configurado():
        print(f'  Transporte  : SMTP ({M.SMTP_HOST}:{M.SMTP_PORT})')
        print(f'  Cuenta      : {M.SMTP_USER}')
        print(f'  Contraseña  : definida ({len(M.SMTP_PASSWORD)} caracteres)')
        if len(M.SMTP_PASSWORD) != 16:
            print('                [!] una App Password de Google tiene 16 caracteres.')
            print('                  Si copiaste los 4 grupos, sacale los espacios.')
    elif M.SENDGRID_API_KEY:
        print('  Transporte  : SendGrid (API HTTP)')
    else:
        print('  Transporte  : NINGUNO')
        print()
        print('  La app no va a mandar nada: solo loguea el intento. El circuito de')
        print('  autorización sigue funcionando igual, pero nadie se entera por mail.')
        print('  Faltan SMTP_HOST + SMTP_USER + SMTP_PASSWORD en el .env.')
        return 1

    desde, nombre = M.remitente()
    destino = sys.argv[1] if len(sys.argv) > 1 else desde
    print(f'  Remitente   : {nombre} <{desde}>')
    print(f'  Responder a : {M.MAIL_REPLY_TO or "(sin Reply-To)"}')
    print(f'  Destinatario: {destino}')
    print()

    cuerpo = f"""
     <p style="margin:0 0 16px; font-size:15px; color:#111827; line-height:1.6;">
       Si estás leyendo esto, el envío de mail de <strong>{M.APP_NOMBRE}</strong>
       quedó funcionando.
     </p>
     <p style="margin:0; padding:14px 16px; background:#f8fafc; border-left:3px solid #e5e7eb; border-radius:8px; font-size:13px; color:#6b7280; line-height:1.6;">
       Es un mail de prueba: no hay que hacer nada con él.
     </p>"""
    texto = (f'Si estás leyendo esto, el envío de mail de {M.APP_NOMBRE} quedó '
             'funcionando.\n\nEs un mail de prueba: no hay que hacer nada con él.')

    print('  Enviando...')
    ok = M.enviar_mail(destino, f'Prueba de envío - {M.APP_NOMBRE}', texto,
                       M.mail_layout('Prueba de envío', cuerpo))
    print()
    if ok:
        print('  [OK] El proveedor lo acepto.')
        print(f'     Revisá {destino} (mirá también spam/promociones).')
        print('     Chequeá TRES cosas en el mail que llega:')
        print(f'       1. El remitente dice "{nombre}".')
        print('       2. El header de color se ve con los dos logos.')
        print('       3. El link del botón apunta al dominio de PUBLIC_BASE_URL.')
        return 0

    print('  [ERROR] No se pudo enviar. El detalle esta en el traceback de arriba.')
    print()
    print('  Lo más común, en orden:')
    print('   - 535 Username and Password not accepted -> no es una App Password')
    print('     válida. Tiene que estar activada la verificación en 2 pasos y la')
    print('     clave se genera en myaccount.google.com/apppasswords.')
    print('   - La contrasena se pego con los espacios de los 4 grupos.')
    print('   - SMTP_USER no es exactamente la casilla que genero la App Password.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
