"""Clave de administración: protege las acciones sensibles del panel de Autorizados
(generar código de alta, blanquear PIN, desbloquear).

La clave se configura en el despliegue con la variable de entorno ADMIN_PASSWORD
(la setea administración / IT). Si no está configurada, se usa una por defecto y se
avisa, para que nadie quede con el panel abierto sin darse cuenta.
"""

import hmac
import os
from functools import wraps

from flask import jsonify, request

CLAVE_DEFAULT = 'neostar-admin'

# Claves de ejemplo que no protegen nada: la del código y la que pone el compose cuando
# el .env no define ADMIN_PASSWORD. Con cualquiera de las dos, el panel avisa.
CLAVES_DE_EJEMPLO = {CLAVE_DEFAULT, 'cambiar-esta-clave'}


def clave_actual():
    return os.environ.get('ADMIN_PASSWORD') or CLAVE_DEFAULT


def usando_default():
    return clave_actual() in CLAVES_DE_EJEMPLO


def verificar_admin(clave):
    return bool(clave) and hmac.compare_digest(str(clave), clave_actual())


def requiere_admin(fn):
    """Exige la clave de administración (header X-Admin-Password) en una ruta."""
    @wraps(fn)
    def envoltorio(*args, **kwargs):
        if not verificar_admin(request.headers.get('X-Admin-Password', '')):
            return jsonify({'error': 'Clave de administración incorrecta o no ingresada'}), 401
        return fn(*args, **kwargs)
    return envoltorio
