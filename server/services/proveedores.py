"""Datos de un proveedor tomados de sus solicitudes anteriores, para no tipearlos de nuevo.

No hay un maestro de proveedores: el proveedor vive en cada solicitud. Con el CUIT se
buscan las anteriores y, de cada dato, se toma el más reciente que esté cargado (el
legajo puede estar en una solicitud vieja y el teléfono en la última).
"""

from models.database import get_db
from services.cuit import solo_digitos

# Datos que se completan solos. El legajo va de a par (archivo + nombre de la misma
# solicitud), igual que la imagen del CBU con el número.
_SUELTOS = ('proveedor_nombre', 'contacto_nombre', 'contacto_telefono', 'contacto_mail')
_PARES = (('legajo_archivo', 'legajo_nombre'), ('cbu', 'cbu_imagen'))


def datos_previos(cuit):
    """{'encontrado': False} o {'encontrado': True, 'solicitudes': n, 'ultima_id': id,
    'datos': {...}} con lo más reciente de cada dato."""
    digitos = solo_digitos(cuit)
    if len(digitos) != 11:
        return {'encontrado': False}
    columnas = ', '.join(_SUELTOS + tuple(c for par in _PARES for c in par))
    conn = get_db()
    try:
        filas = conn.execute(
            f'SELECT id, {columnas} FROM solicitudes '
            "WHERE REPLACE(REPLACE(REPLACE(cuit, '-', ''), ' ', ''), '.', '') = ? ORDER BY id DESC",
            (digitos,)).fetchall()
    finally:
        conn.close()
    if not filas:
        return {'encontrado': False}

    datos = {}
    for campo in _SUELTOS:
        valor = next((f[campo] for f in filas if str(f[campo] or '').strip()), '')
        if valor:
            datos[campo] = valor
    for principal, acompanante in _PARES:
        fila = next((f for f in filas if str(f[principal] or '').strip()
                     or str(f[acompanante] or '').strip()), None)
        if fila:
            datos[principal], datos[acompanante] = fila[principal], fila[acompanante]
    return {'encontrado': True, 'solicitudes': len(filas), 'ultima_id': filas[0]['id'], 'datos': datos}
