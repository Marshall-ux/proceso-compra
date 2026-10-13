"""Moneda de las solicitudes: pesos (ARS) o dólares (USD).

Los topes de los autorizantes están en pesos. Una solicitud en dólares guarda el tipo
de cambio que cargó quien la subió, y todo control contra los topes (alcanza una firma
o hace falta otra, a quién se puede avisar) se hace con el equivalente en pesos.
"""

MONEDAS = ('ARS', 'USD')
SIMBOLOS = {'ARS': '$', 'USD': 'U$S'}


def normalizar(moneda):
    """'usd' -> 'USD'; vacío o desconocido -> 'ARS' (las solicitudes viejas son en pesos)."""
    m = str(moneda or '').strip().upper()
    return m if m in MONEDAS else 'ARS'


def simbolo(moneda):
    return SIMBOLOS[normalizar(moneda)]


def tipo_cambio(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def en_pesos(monto, moneda, cambio):
    """Equivalente en pesos de un monto, para compararlo con los topes."""
    try:
        monto = float(monto or 0)
    except (TypeError, ValueError):
        monto = 0.0
    if normalizar(moneda) == 'USD':
        return round(monto * tipo_cambio(cambio), 2)
    return monto
