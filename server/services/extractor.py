"""Extraccion de datos desde el PDF de una factura de compra.

A diferencia de las facturas de terminales (que tienen un formato fijo por marca), las
facturas de proveedores vienen en formatos muy distintos, asi que este extractor es
generico y heuristico: saca lo que puede y marca en `faltantes` lo que el empleado
tiene que completar a mano. La revision manual siempre existe.
"""

import re
import unicodedata

import pdfplumber

from services.marcas import EMPRESAS

# CUITs del grupo: nunca son el proveedor, son el cliente (quien compra).
CUITS_GRUPO = {'34-68473349-6'}

# Como aparece cada empresa del grupo en la factura -> valor del formulario.
_ALIAS_EMPRESAS = {
    'ALCO ROSARIO': 'ALCO ROSARIO S.A.',
    'NEOSTAR': 'NEOSTAR S.A.',
    'XINOXIA': 'XINOXIA S.A.',
    'DASEOS': 'DASEOS S.A.',
    'HIKARI': 'HIKARI S.A.',
}

_RE_CUIT = re.compile(r'\b(\d{2}-\d{8}-\d)\b')
_RE_CUIT_PLANO = re.compile(r'(?<!\d)(\d{11})(?!\d)')
_RE_FECHA = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b')
_RE_NUMERO = re.compile(r'(?:N[º°ro\.]*\s*)?(\d{4}-\d{8})\b')
_RE_MAIL = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b')
_RE_CBU = re.compile(r'(?<!\d)(\d{22})(?!\d)')
_RE_TEL = re.compile(r'(?:tel|telefono|tel\.|wsp|whatsapp|cel)[\s.:]*([\d\s()\-]{7,20})', re.I)
_RE_IMPORTE = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2}')

# Palabras que descartan una linea como item del detalle.
_NO_ITEM = (
    'subtotal', 'total', 'iva', 'dto', 'descuento', 'importe neto', 'cae', 'comprobante',
    'valor de referencia', 'percepcion', 'percepciones', 'cod.', 'cant.', 'descripcion',
    'decripcion', 'vencimiento', 'pagina', 'condicion',
)


def _norm(texto):
    """Minusculas sin acentos, para comparar."""
    s = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


def parse_importe(valor):
    """'27.350,00' -> 27350.0 (formato argentino)."""
    if valor is None:
        return 0.0
    s = str(valor).strip().replace('$', '').replace(' ', '')
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def extraer_texto(path):
    partes = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            partes.append(page.extract_text() or '')
    return '\n'.join(partes)


def _cuit_proveedor(texto, lineas):
    """Primer CUIT que no sea de una empresa del grupo (el cliente)."""
    candidatos = []
    for linea in lineas:
        for cuit in _RE_CUIT.findall(linea):
            candidatos.append((cuit, linea))
        for plano in _RE_CUIT_PLANO.findall(linea):
            candidatos.append((f'{plano[:2]}-{plano[2:10]}-{plano[10]}', linea))

    for cuit, linea in candidatos:
        if cuit in CUITS_GRUPO:
            continue
        # Si la linea nombra a una empresa del grupo, ese CUIT es el del cliente.
        if any(alias in _norm(linea) for alias in map(_norm, _ALIAS_EMPRESAS)):
            continue
        return cuit
    return ''


def _nombre_proveedor(lineas):
    """El proveedor suele ser la razon social del encabezado (primeras lineas),
    antes de cualquier mencion al cliente."""
    for linea in lineas[:6]:
        limpia = linea.strip()
        if len(limpia) < 3:
            continue
        n = _norm(limpia)
        if any(alias in n for alias in map(_norm, _ALIAS_EMPRESAS)):
            continue
        if any(p in n for p in ('factura', 'presupuesto', 'remito', 'nota de', 'cod.', 'original')):
            # Puede venir pegado: "Daniel Omar Oriti A FACTURA" -> corto antes.
            corte = re.split(r'\s+(?:FACTURA|PRESUPUESTO|REMITO)', limpia)[0].strip()
            corte = re.sub(r'\s+[A-C]$', '', corte).strip()
            if len(corte) >= 3:
                return corte
            continue
        return re.sub(r'\s+[A-C]$', '', limpia).strip()
    return ''


def _empresa(texto):
    n = _norm(texto)
    for alias, valor in _ALIAS_EMPRESAS.items():
        if _norm(alias) in n:
            return valor
    return ''


def _fecha(texto, lineas):
    for linea in lineas:
        if 'fecha' in _norm(linea) and 'vto' not in _norm(linea) and 'vencimiento' not in _norm(linea):
            m = _RE_FECHA.search(linea)
            if m:
                return _normalizar_fecha(m.group(1))
    m = _RE_FECHA.search(texto)
    return _normalizar_fecha(m.group(1)) if m else ''


def _normalizar_fecha(f):
    """-> dd/mm/aaaa"""
    partes = re.split(r'[/-]', f)
    if len(partes) != 3:
        return f
    d, m, a = partes
    if len(a) == 2:
        a = '20' + a
    return f'{int(d):02d}/{int(m):02d}/{a}'


def _numero_factura(texto):
    for m in _RE_NUMERO.finditer(texto):
        return m.group(1)
    return ''


def _total(texto, lineas):
    """El TOTAL final; si no aparece, se cae al importe mas grande del documento."""
    for linea in reversed(lineas):
        n = _norm(linea)
        if re.search(r'\btotal\b', n) and 'subtotal' not in n:
            importes = _RE_IMPORTE.findall(linea)
            if importes:
                return parse_importe(importes[-1])
    importes = [parse_importe(i) for i in _RE_IMPORTE.findall(texto)]
    return max(importes) if importes else 0.0


def _items(lineas):
    """Filas del detalle: cantidad + descripcion + total."""
    items = []
    for linea in lineas:
        n = _norm(linea)
        if any(p in n for p in _NO_ITEM):
            continue
        m = re.match(r'^\s*(?:\d+\s+)?([\d.]+,\d{2}|\d+)\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$', linea)
        if not m:
            continue
        cantidad = parse_importe(m.group(1))
        descripcion = m.group(2).strip()
        total = parse_importe(m.group(3))
        if not descripcion or cantidad <= 0:
            continue
        # Una descripcion que es solo numeros no es un item real.
        if not re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]', descripcion):
            continue
        precio = round(total / cantidad, 2) if cantidad else 0.0
        items.append({
            'descripcion': descripcion,
            'cantidad': cantidad,
            'precio': precio,
            'total': total,
        })
    return items


def _condiciones_pago(texto):
    """Devuelve (condicion_pago, condicion_dias)."""
    n = _norm(texto)
    m = re.search(r'(?:cta\.?\s*cte\.?|cuenta corriente)\D{0,15}(\d{1,3})\s*dias', n)
    if m:
        return 'cuenta_corriente', m.group(1)
    if 'cta. cte' in n or 'cuenta corriente' in n or 'cta.cte' in n:
        return 'cuenta_corriente', ''
    if 'contado' in n:
        return 'contado', ''
    return '', ''


def _contacto(texto, lineas):
    mail = _RE_MAIL.search(texto)
    telefono = ''
    for linea in lineas:
        m = _RE_TEL.search(linea)
        if m:
            telefono = re.sub(r'\s+', ' ', m.group(1)).strip()
            break
    return (mail.group(0) if mail else ''), telefono


def extraer_datos_factura(path):
    """Devuelve un dict con los campos del formulario que se pudieron inferir."""
    texto = extraer_texto(path)
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]

    if not lineas:
        return {
            'ok': False,
            'error': 'El PDF no tiene texto seleccionable (probablemente sea un escaneo). '
                     'Cargá los datos a mano.',
            'datos': {},
            'items': [],
            'faltantes': [],
        }

    condicion_pago, condicion_dias = _condiciones_pago(texto)
    mail, telefono = _contacto(texto, lineas)
    cbu = _RE_CBU.search(texto)
    items = _items(lineas)
    total = _total(texto, lineas)

    datos = {
        'fecha': _fecha(texto, lineas),
        'empresa': _empresa(texto),
        'proveedor_nombre': _nombre_proveedor(lineas),
        'cuit': _cuit_proveedor(texto, lineas),
        'monto_total': total,
        'factura_numero': _numero_factura(texto),
        'condicion_pago': condicion_pago,
        'condicion_dias': condicion_dias,
        'contacto_mail': mail,
        'contacto_telefono': telefono,
        'cbu': cbu.group(1) if cbu else '',
    }

    # Campos que el formulario necesita y la factura nunca trae.
    faltantes = [k for k in ('marca', 'concepto', 'proveedor_tipo', 'tipo_orden', 'solicitado_por')]
    faltantes += [k for k, v in datos.items() if not v and k not in ('cbu', 'factura_numero')]

    return {'ok': True, 'error': '', 'datos': datos, 'items': items, 'faltantes': faltantes}
