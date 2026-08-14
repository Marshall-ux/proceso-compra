"""Armado del ZIP con todo lo de una solicitud, para archivar en el disco interno.

Cada ZIP trae la autorización, las facturas, el legajo, la imagen del CBU y un
resumen.txt para que la carpeta se entienda sin abrir la app.
"""

import io
import os
import re
import unicodedata
import zipfile

from services.marcas import CONCEPTOS
from services.pdf_fill import fmt_fecha_hora, fmt_money, generar_pdf

UPLOADS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
GENERADOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'generated')

CRITICIDADES = {
    'urgente': 'URGENTE',
    'informado': 'Informado en factura',
    'otro': 'Otro',
}


def _slug(texto, largo=40):
    """'Daniel Omar Oriti' -> 'Daniel-Omar-Oriti' (apto para nombre de archivo)."""
    s = unicodedata.normalize('NFKD', str(texto or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-')
    return s[:largo] or 'sin-proveedor'


def _fecha_archivo(solicitud):
    """created_at '2026-07-20 09:15:00' -> '2026-07-20'."""
    return str(solicitud.get('created_at') or '')[:10] or 'sin-fecha'


def nombre_zip(solicitud):
    return (f'{_fecha_archivo(solicitud)}_Solicitud-{solicitud["id"]:04d}_'
            f'{_slug(solicitud.get("proveedor_nombre"))}.zip')


def _resumen(solicitud):
    """Texto plano con los datos principales, para leer desde el disco."""
    estado = 'AUTORIZADA' if solicitud.get('estado') == 'autorizada' else 'PENDIENTE DE AUTORIZACIÓN'
    concepto = CONCEPTOS.get(solicitud.get('concepto'), solicitud.get('concepto') or '')
    if solicitud.get('concepto') == 'otros' and solicitud.get('concepto_otro'):
        concepto += f' ({solicitud["concepto_otro"]})'
    criticidad = CRITICIDADES.get(solicitud.get('criticidad'), solicitud.get('criticidad') or '-')
    if solicitud.get('criticidad') == 'otro' and solicitud.get('criticidad_obs'):
        criticidad += f' ({solicitud["criticidad_obs"]})'

    lineas = [
        f'SOLICITUD #{solicitud["id"]} - {estado}',
        '=' * 60,
        f'Fecha de la factura : {solicitud.get("fecha") or "-"}',
        f'Cargada el          : {fmt_fecha_hora(solicitud.get("created_at"))}',
        f'Empresa             : {", ".join(solicitud.get("empresas") or []) or solicitud.get("empresa") or "-"}',
        f'Marca               : {", ".join(solicitud.get("marcas") or []) or solicitud.get("marca") or "-"}',
        f'Proveedor           : {solicitud.get("proveedor_nombre") or "-"}',
        f'CUIT                : {solicitud.get("cuit") or "-"}',
        f'Concepto            : {concepto or "-"}',
        f'Criticidad          : {criticidad}',
        f'Requiere OC         : {(solicitud.get("requiere_oc") or "-").upper()}',
        f'Cargado en Autopack : {"SI" if solicitud.get("autopack_ok") else "NO"}',
        f'MONTO TOTAL         : $ {fmt_money(solicitud.get("monto_total"))}',
        f'Solicitado por      : {solicitud.get("solicitado_por") or "-"}',
        '',
        'DETALLE',
        '-' * 60,
    ]
    for it in solicitud.get('items', []):
        lineas.append(f'  {it.get("descripcion", ""):<40} '
                      f'{fmt_money(it.get("total")):>14}')

    lineas += ['', 'AUTORIZACIONES', '-' * 60]
    if solicitud.get('autorizaciones'):
        for a in solicitud['autorizaciones']:
            extra = ' [EXCEDE SU TOPE]' if a.get('excedio_tope') else ''
            lineas.append(f'  {a.get("nombre", "")} - {a.get("cargo", "")} - '
                          f'{fmt_fecha_hora(a.get("fecha"))}{extra}')
    else:
        lineas.append('  (sin autorizaciones todavía)')

    lineas += ['', 'ARCHIVOS ADJUNTOS', '-' * 60]
    for f in solicitud.get('facturas', []):
        lineas.append(f'  facturas/{f.get("nombre", "")}')
    if solicitud.get('legajo_archivo'):
        lineas.append(f'  {solicitud.get("legajo_nombre") or "legajo.pdf"}')
    if solicitud.get('cbu_imagen'):
        lineas.append('  CBU (imagen)')

    return '\n'.join(lineas) + '\n'


def _agregar_adjunto(zf, archivo, destino):
    ruta = os.path.normpath(os.path.join(UPLOADS, archivo or ''))
    if archivo and ruta.startswith(os.path.normpath(UPLOADS)) and os.path.exists(ruta):
        zf.write(ruta, destino)
        return True
    return False


def _escribir_solicitud(zf, solicitud, prefijo=''):
    """Vuelca una solicitud completa dentro del zip, bajo `prefijo`."""
    os.makedirs(GENERADOS, exist_ok=True)
    pdf = os.path.join(GENERADOS, f'autorizacion-{solicitud["id"]}.pdf')
    generar_pdf(solicitud, pdf)
    zf.write(pdf, f'{prefijo}Autorizacion-{solicitud["id"]:04d}.pdf')
    zf.writestr(f'{prefijo}resumen.txt', _resumen(solicitud))

    for i, f in enumerate(solicitud.get('facturas', []), start=1):
        nombre = f.get('nombre') or f'factura-{i}.pdf'
        _agregar_adjunto(zf, f.get('archivo'), f'{prefijo}facturas/{i:02d}-{nombre}')

    if solicitud.get('legajo_archivo'):
        _agregar_adjunto(zf, solicitud['legajo_archivo'],
                         f'{prefijo}{solicitud.get("legajo_nombre") or "legajo.pdf"}')

    if solicitud.get('cbu_imagen'):
        ext = os.path.splitext(solicitud['cbu_imagen'])[1] or '.jpg'
        _agregar_adjunto(zf, solicitud['cbu_imagen'], f'{prefijo}CBU{ext}')


def armar_zip(solicitud):
    """ZIP de una sola solicitud."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        _escribir_solicitud(zf, solicitud)
    buffer.seek(0)
    return buffer


def armar_zip_lote(solicitudes):
    """ZIP con varias solicitudes, cada una en su carpeta."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for s in solicitudes:
            carpeta = nombre_zip(s)[:-4]  # mismo nombre, sin .zip
            _escribir_solicitud(zf, s, prefijo=f'{carpeta}/')
    buffer.seek(0)
    return buffer
