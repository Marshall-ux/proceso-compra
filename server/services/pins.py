"""PIN de los autorizados: alta con código de un solo uso, bloqueo por intentos y auditoría.

No se guarda nada en claro: ni el PIN ni el código de alta (PBKDF2-HMAC-SHA256 con
salt por persona).

Por qué el código de alta: sin él, la primera persona que eligiera a un autorizante
podría fijarle el PIN y quedarse con su firma. El admin genera el código, se lo
entrega a la persona, y recién con ese código puede definir su PIN.
"""

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta

ITERATIONS = 120_000

# PIN de 6 a 8 dígitos: 4 son demasiado pocos para algo que autoriza pagos.
PIN_RE = re.compile(r'^\d{6,8}$')

# Intentos fallidos antes de bloquear, y cuánto dura el bloqueo.
MAX_INTENTOS = 5
BLOQUEO_MINUTOS = 15

# Alfabeto del código de alta, sin caracteres que se confunden al dictarlo (O/0, I/1).
_ALFABETO_CODIGO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
LARGO_CODIGO = 8

_FORMATO_FECHA = '%Y-%m-%d %H:%M:%S'


# ----------------------------- política de PIN -----------------------------
def _trivial(pin):
    """Rechaza PINs adivinables: todos iguales o secuencias."""
    if len(set(pin)) == 1:                       # 111111
        return True
    ascendente = all(int(pin[i + 1]) - int(pin[i]) == 1 for i in range(len(pin) - 1))
    descendente = all(int(pin[i]) - int(pin[i + 1]) == 1 for i in range(len(pin) - 1))
    return ascendente or descendente             # 123456 / 654321


def validar_pin(pin):
    """Devuelve un mensaje de error, o '' si el PIN sirve."""
    pin = str(pin or '')
    if not PIN_RE.match(pin):
        return 'El PIN debe tener entre 6 y 8 dígitos'
    if _trivial(pin):
        return 'Ese PIN es demasiado fácil de adivinar: evitá secuencias o dígitos repetidos'
    return ''


def pin_valido(pin):
    return validar_pin(pin) == ''


# ------------------------------- hashing ------------------------------------
def _hash(valor):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', valor.encode(), salt, ITERATIONS)
    return f'{salt.hex()}${dk.hex()}'


def _verificar(valor, guardado):
    if not guardado or not valor:
        return False
    try:
        salt_hex, dk_hex = guardado.split('$')
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac('sha256', valor.encode(), bytes.fromhex(salt_hex), ITERATIONS)
    return hmac.compare_digest(dk.hex(), dk_hex)


hash_pin = _hash
verificar_pin = _verificar


# --------------------------- código de alta ---------------------------------
def generar_codigo():
    """Devuelve (codigo_en_claro, hash). El claro se muestra una sola vez."""
    codigo = ''.join(secrets.choice(_ALFABETO_CODIGO) for _ in range(LARGO_CODIGO))
    return codigo, _hash(codigo)


def verificar_codigo(codigo, guardado):
    return _verificar(str(codigo or '').strip().upper(), guardado)


# ------------------------------- bloqueo ------------------------------------
def esta_bloqueado(bloqueado_hasta):
    """(bloqueado, minutos_restantes)"""
    if not bloqueado_hasta:
        return False, 0
    try:
        hasta = datetime.strptime(bloqueado_hasta, _FORMATO_FECHA)
    except ValueError:
        return False, 0
    restante = hasta - datetime.now()
    if restante.total_seconds() <= 0:
        return False, 0
    return True, max(1, int(restante.total_seconds() // 60) + 1)


def momento_desbloqueo():
    return (datetime.now() + timedelta(minutes=BLOQUEO_MINUTOS)).strftime(_FORMATO_FECHA)


# ------------------------------ auditoría -----------------------------------
def registrar_intento(conn, autorizado_id, resultado, solicitud_id=None):
    conn.execute(
        'INSERT INTO intentos_pin (autorizado_id, solicitud_id, resultado) VALUES (?, ?, ?)',
        (autorizado_id, solicitud_id, resultado),
    )
