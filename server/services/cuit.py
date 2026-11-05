"""CUIT: formato y dígito verificador.

El CUIT del proveedor es obligatorio y se valida (decisión del 5-11-2026): con un número
mal tipeado no se encuentra al proveedor para autocompletarlo, no se detectan las
órdenes abiertas repetidas y queda mal en el formulario oficial.
"""

import re

_PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def solo_digitos(cuit):
    return re.sub(r'\D', '', str(cuit or ''))


def es_valido(cuit):
    """11 dígitos y el último coincide con el verificador (módulo 11)."""
    d = solo_digitos(cuit)
    if len(d) != 11:
        return False
    resto = sum(int(x) * p for x, p in zip(d[:10], _PESOS)) % 11
    verificador = 0 if resto == 0 else 11 - resto
    return verificador != 10 and verificador == int(d[10])


def formatear(cuit):
    """'30712345671' -> '30-71234567-1'. Si no tiene 11 dígitos lo deja como vino."""
    d = solo_digitos(cuit)
    return f'{d[:2]}-{d[2:10]}-{d[10]}' if len(d) == 11 else str(cuit or '').strip()
