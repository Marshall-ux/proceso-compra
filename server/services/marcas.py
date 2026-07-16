"""Que planilla de autorizados aplica para cada marca del formulario F 8.4-01.

Los autorizados de la planilla MULTIMARCA pueden autorizar cualquier marca, por eso
se agregan siempre.
"""

# Opciones de marca tal como figuran en el formulario.
MARCAS = [
    'FCA', 'HONDA', 'KIA', 'NISSAN', 'SUZUKI', 'SUBARU', 'BYD',
    'SHOWROOM FUNES', 'CAÑADA DE GOMEZ', 'OTRO',
]

EMPRESAS = ['ALCO ROSARIO S.A.', 'NEOSTAR S.A.', 'XINOXIA S.A.', 'DASEOS S.A.', 'HIKARI S.A.']

CONCEPTOS = {
    'publicidad': 'PUBLICIDAD / MARKETING',
    'muebles': 'MUEBLES Y ÚTILES',
    'gastos': 'GASTOS GENERALES',
    'reparacion': 'REPARACIÓN Y MANTENIMIENTO',
    'comisiones': 'COMISIONES Y/O HONORARIOS',
    'otros': 'OTROS',
}

# marca -> listas de autorizados especificas (multimarca se suma aparte).
_LISTAS_POR_MARCA = {
    'NISSAN': ['nissan'],
    'FCA': ['jeep'],           # la planilla "JEEP" es la de Chrysler/FCA
    'KIA': ['kia'],
    'SUZUKI': ['kia'],         # la planilla KIA cubre explicitamente Kia / Suzuki
}


def listas_para_marca(marca):
    """Devuelve las listas de autorizados habilitadas para una marca."""
    return _LISTAS_POR_MARCA.get((marca or '').upper(), []) + ['multimarca']
