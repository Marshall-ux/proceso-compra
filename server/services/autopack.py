"""Quién puede tildar 'cargado en Autopack': solo administración, identificada con su
mail y la clave de Autopack.

La clave se configura en el despliegue con la variable de entorno AUTOPACK_PASSWORD;
si no está, se usa la acordada con administración. Es una clave compartida: sirve para
que nadie tilde por error y para saber quién lo hizo, no para frenar una suplantación.
"""

import hmac
import os

CLAVE_DEFAULT = '12345'

# mail (en minúsculas) -> nombre que queda registrado en la solicitud
HABILITADOS = {
    'bcoll@neostar.com.ar': 'Barbara Coll',
    'nblois@neostar.com.ar': 'Nicole Blois',
    'mlhenning@neostar.com.ar': 'Maria Laura Henning',
    'mspurello@neostar.com.ar': 'Maria Sol Purello',
    'dmorelli@neostar.com.ar': 'Daiana Morelli',
    'evanlesberg@neostar.com.ar': 'Emiliano Vanlesberg',
}


def clave_actual():
    return os.environ.get('AUTOPACK_PASSWORD') or CLAVE_DEFAULT


def identificar(email, clave):
    """Devuelve el nombre de la persona si el mail está habilitado y la clave es
    correcta; si no, None."""
    nombre = HABILITADOS.get(str(email or '').strip().lower())
    if not nombre or not clave:
        return None
    if not hmac.compare_digest(str(clave), clave_actual()):
        return None
    return nombre
