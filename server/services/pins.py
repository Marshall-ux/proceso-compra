"""PIN de los autorizados.

No se guarda el PIN en claro: se guarda PBKDF2-HMAC-SHA256 con salt por persona.
El alta la hace cada autorizado la primera vez que firma.
"""

import hashlib
import hmac
import os
import re

ITERATIONS = 120_000
PIN_RE = re.compile(r'^\d{4,6}$')


def pin_valido(pin):
    return bool(PIN_RE.match(pin or ''))


def hash_pin(pin):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt, ITERATIONS)
    return f'{salt.hex()}${dk.hex()}'


def verificar_pin(pin, pin_hash):
    if not pin_hash or not pin:
        return False
    try:
        salt_hex, dk_hex = pin_hash.split('$')
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac('sha256', pin.encode(), bytes.fromhex(salt_hex), ITERATIONS)
    return hmac.compare_digest(dk.hex(), dk_hex)
