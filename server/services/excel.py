"""La lista de solicitudes en Excel (.xlsx), con los mismos filtros de la pantalla.

Se arma en memoria, como el PDF. Los montos y las fechas de carga van como número y
fecha de verdad (no como texto), para poder sumar, ordenar y filtrar en Excel.
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from services import moneda as mon
from services.marcas import CONCEPTOS, UBICACIONES
from services.paquete import CRITICIDADES
from services.solicitudes import lista_multi

ESTADOS = {
    'pendiente': 'Pendiente',
    'autorizada': 'Autorizada',
    'observada': 'Devuelta para corregir',
    'rechazada': 'Rechazada',
}
_FORMATO_MONTO = '#,##0.00'


def _cargada(s):
    try:
        return datetime.strptime(str(s.get('created_at') or '')[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def _firmante(s):
    """Quién la firmó, la devolvió o la rechazó; si está pendiente, a quién espera."""
    if s.get('estado') == 'autorizada':
        return s.get('firmado_por') or ''
    if s.get('estado') in ('observada', 'rechazada'):
        return s.get('revision_por') or ''
    return s.get('firmante') or 'Cualquier habilitado'


def _concepto(s):
    if s.get('concepto') == 'otros' and s.get('concepto_otro'):
        return f'OTROS ({s["concepto_otro"]})'
    return CONCEPTOS.get(s.get('concepto'), s.get('concepto') or '')


# (título, valor, ancho, formato numérico)
COLUMNAS = (
    ('N°', lambda s: s['id'], 7, None),
    ('Cargada', _cargada, 17, 'dd/mm/yyyy hh:mm'),
    ('Fecha factura', lambda s: s.get('fecha') or '', 13, None),
    ('Proveedor', lambda s: s.get('proveedor_nombre') or '', 32, None),
    ('CUIT', lambda s: s.get('cuit') or '', 15, None),
    ('Empresa', lambda s: ', '.join(lista_multi(s, 'empresas', 'empresa')), 22, None),
    ('Marca', lambda s: ', '.join(lista_multi(s, 'marcas', 'marca')), 16, None),
    ('Ubicación', lambda s: UBICACIONES.get(s.get('ubicacion'), s.get('ubicacion') or ''), 11, None),
    ('Concepto', _concepto, 26, None),
    ('Criticidad', lambda s: CRITICIDADES.get(s.get('criticidad'), s.get('criticidad') or ''), 18, None),
    ('Moneda', lambda s: mon.normalizar(s.get('moneda')), 8, None),
    ('Monto', lambda s: float(s.get('monto_total') or 0), 15, _FORMATO_MONTO),
    ('Tipo de cambio', lambda s: float(s.get('tipo_cambio') or 0) or None, 13, _FORMATO_MONTO),
    ('Monto en pesos', lambda s: mon.en_pesos(s.get('monto_total'), s.get('moneda'), s.get('tipo_cambio')),
     16, _FORMATO_MONTO),
    ('Estado', lambda s: ESTADOS.get(s.get('estado'), s.get('estado') or ''), 20, None),
    ('Firmante', _firmante, 24, None),
    ('Motivo (devuelta / rechazada)', lambda s: (s.get('revision_motivo') or '')
     if s.get('estado') in ('observada', 'rechazada') else '', 34, None),
    ('Solicitado por', lambda s: s.get('solicitado_por') or '', 20, None),
    ('Autopack', lambda s: 'Sí' if s.get('autopack_ok') else 'No', 10, None),
)


def armar(solicitudes):
    """Devuelve el .xlsx en un BytesIO: una fila por solicitud, encabezado fijo y filtros."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Solicitudes'
    hoja.append([titulo for titulo, _, _, _ in COLUMNAS])
    for celda in hoja[1]:
        celda.font = Font(bold=True)
        celda.fill = PatternFill('solid', fgColor='E8F8EE')
        celda.alignment = Alignment(vertical='center')
    for s in solicitudes:
        hoja.append([valor(s) for _, valor, _, _ in COLUMNAS])
    for i, (_, _, ancho, formato) in enumerate(COLUMNAS, start=1):
        letra = get_column_letter(i)
        hoja.column_dimensions[letra].width = ancho
        if formato:
            for (celda,) in hoja.iter_rows(min_row=2, min_col=i, max_col=i):
                celda.number_format = formato
    hoja.freeze_panes = 'A2'
    hoja.auto_filter.ref = hoja.dimensions

    salida = io.BytesIO()
    libro.save(salida)
    salida.seek(0)
    return salida
