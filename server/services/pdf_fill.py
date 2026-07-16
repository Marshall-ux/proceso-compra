"""Completa el formulario oficial 'F 8.4-01 - Autorizacion Generica de compra o
contratacion' Rev. 07.

No se redibuja nada: se usa el PDF original de la empresa como base (assets/) y se
escriben los valores en las coordenadas que definen sus propios campos AcroForm.
La salida se aplana (texto fijo, sin campos editables): una autorizacion firmada no
se tiene que poder modificar despues.

Si algun dia sale un Rev.08, se reemplaza el PDF de assets/ y se revisa MAPA_CAMPOS.
"""

import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor, black
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PLANTILLA = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets',
                         'formulario_f8401_rev07.pdf')

ROJO = HexColor('#b00020')
GRIS = HexColor('#8a93a0')

# El formulario no imprime los casilleros en la hoja: cada campo los dibuja en su
# propio "appearance" (fondo blanco, borde gris). Al aplanar hay que reproducirlos
# con los mismos colores para que la salida se vea igual al original.
CASILLA_BORDE = HexColor('#ABADB3')

# --------------------------------------------------------------------------
# Mapa de los campos del PDF original. Los nombres (Text23, Button7...) son los
# que trae el formulario; se identificaron por su posicion en la hoja.
# --------------------------------------------------------------------------
CAMPO_FECHA = 'Text23'
CAMPO_PROVEEDOR = 'Text34'
CAMPO_CUIT = 'Text35'
CAMPO_MARCA_OTRO = 'Text22'
CAMPO_MONTO_FINAL = 'Text60'
CAMPO_CBU = 'Text61'
CAMPO_DIAS_OTRO = 'Text69'
CAMPO_CONTACTO = 'Text74'
CAMPO_TELEFONO = 'Text75'
CAMPO_MAIL = 'Text76'
CAMPO_OBSERVACIONES = 'Text77'

EMPRESAS = {
    'ALCO ROSARIO S.A.': 'Button7',
    'NEOSTAR S.A.': 'Button8',
    'XINOXIA S.A.': 'Button9',
    'DASEOS S.A.': 'Button10',
    'HIKARI S.A.': 'Button11',
}

MARCAS = {
    'FCA': 'Button12',
    'HONDA': 'Button13',
    'KIA': 'Button14',
    'NISSAN': 'Button15',
    'SUZUKI': 'Button17',
    'SUBARU': 'Button18',
    'BYD': 'Button16',
    'SHOWROOM FUNES': 'Button19',
    'CAÑADA DE GOMEZ': 'Button20',
    'OTRO': 'Button21',
}

PROVEEDOR_TIPO = {'nuevo': 'Button24', 'habitual': 'Button25'}
TIPO_ORDEN = {'cerrada': 'Button26', 'abierta': 'Button27'}

CONCEPTOS = {
    'publicidad': 'Button28',
    'muebles': 'Button30',
    'gastos': 'Button32',
    'reparacion': 'Button33',
    'comisiones': 'Button29',
    'otros': 'Button31',
}

FORMA_PAGO = {
    'efectivo': 'Button62',
    'cheque': 'Button63',
    'echeq': 'Button64',
    'transferencia': 'Button65',
}

CONDICION_PAGO = {'contado': 'Button66', 'cuenta_corriente': 'Button67', 'otras': 'Button68'}
CONDICION_DIAS = {'7': 'Button70', '20': 'Button71', '30': 'Button72'}
CONDICION_DIAS_OTRO = 'Button73'

# Las 6 filas del detalle: (descripcion, precio, cantidad, total)
FILAS_ITEMS = [
    ('Text36', 'Text47', 'Text57', 'Text53'),
    ('Text37', 'Text46', 'Text59', 'Text56'),
    ('Text38', 'Text45', 'Text58', 'Text50'),
    ('Text39', 'Text42', 'Text51', 'Text48'),
    ('Text40', 'Text43', 'Text52', 'Text54'),
    ('Text41', 'Text44', 'Text49', 'Text55'),
]
MAX_ITEMS = len(FILAS_ITEMS)

# Zonas que el formulario dibuja pero no expone como campo rellenable: se escriben
# directamente sobre la linea de puntos del original. (x0, y0, x1, y1)
ZONA_DURACION_ORDEN = (415.0, 521.0, 532.8, 533.0)
ZONA_CONCEPTO_OTRO = (247.0, 451.5, 532.8, 463.0)
ZONA_CONDICION_OTRAS = (437.0, 202.5, 532.8, 214.0)

# Recuadros de firma del original (tampoco son campos).
CAJA_SOLICITANTE = (54.4, 69.0, 293.7, 113.4)
CAJA_AUTORIZANTES = (301.5, 69.0, 540.8, 113.4)


def fmt_money(valor):
    """1234567.5 -> '1.234.567,50'"""
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        return ''
    entero, dec = f'{v:,.2f}'.split('.')
    return f'{entero.replace(",", ".")},{dec}'


def fmt_fecha_hora(valor):
    """'2026-07-16 14:01:37' -> '16/07/2026 14:01' (formato local)."""
    texto = str(valor or '')
    try:
        fecha, hora = texto.split(' ')
        a, m, d = fecha.split('-')
        return f'{d}/{m}/{a} {hora[:5]}'
    except ValueError:
        return texto


def fmt_cant(valor):
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        return ''
    return str(int(v)) if v == int(v) else fmt_money(v)


def _leer_rects():
    """Posicion de cada campo, leida del propio formulario original."""
    reader = PdfReader(PLANTILLA)
    rects = {}
    for annot in reader.pages[0].get('/Annots', []):
        obj = annot.get_object()
        nombre = obj.get('/T')
        if nombre and obj.get('/Rect'):
            x0, y0, x1, y1 = (float(v) for v in obj['/Rect'])
            rects[str(nombre)] = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    return rects


RECTS = _leer_rects()


class _Overlay:
    """Capa de texto que se imprime encima del formulario original."""

    def __init__(self):
        self.buffer = io.BytesIO()
        self.c = canvas.Canvas(self.buffer, pagesize=(595.32, 841.92))
        self.c.setFillColor(black)

    # ------------------------------- helpers -------------------------------
    def _recortar(self, texto, ancho, fuente, size):
        if stringWidth(texto, fuente, size) <= ancho:
            return texto
        while texto and stringWidth(texto + '…', fuente, size) > ancho:
            texto = texto[:-1]
        return texto + '…'

    def texto_en(self, rect, valor, size=8, bold=False, alinear='izq', color=black):
        if valor in (None, '') or not rect:
            return
        x0, y0, x1, y1 = rect
        fuente = 'Helvetica-Bold' if bold else 'Helvetica'
        texto = self._recortar(str(valor), (x1 - x0) - 4, fuente, size)
        self.c.setFillColor(color)
        self.c.setFont(fuente, size)
        y = y0 + ((y1 - y0) - size) / 2 + 1.4
        if alinear == 'der':
            self.c.drawRightString(x1 - 3, y, texto)
        elif alinear == 'centro':
            self.c.drawCentredString((x0 + x1) / 2, y, texto)
        else:
            self.c.drawString(x0 + 3, y, texto)
        self.c.setFillColor(black)

    def campo(self, nombre, valor, **kw):
        self.texto_en(RECTS.get(nombre), valor, **kw)

    def casilla(self, nombre, marcado=False):
        """Dibuja el casillero tal como lo hace el formulario original y, si
        corresponde, lo tilda."""
        rect = RECTS.get(nombre)
        if not rect:
            return
        x0, y0, x1, y1 = rect
        self.c.setFillColorRGB(1, 1, 1)
        self.c.setStrokeColor(CASILLA_BORDE)
        self.c.setLineWidth(1)
        self.c.rect(x0 + 0.5, y0 + 0.5, (x1 - x0) - 1, (y1 - y0) - 1, stroke=1, fill=1)
        if marcado:
            size = min(x1 - x0, y1 - y0) * 0.78
            self.c.setFillColor(black)
            self.c.setFont('Helvetica-Bold', size)
            self.c.drawCentredString((x0 + x1) / 2, (y0 + y1) / 2 - size * 0.34, 'X')
        self.c.setFillColor(black)

    def guardar(self):
        self.c.showPage()
        self.c.save()
        self.buffer.seek(0)
        return self.buffer


def _firmas(ov, solicitud):
    """El original trae un unico recuadro 'AUTORIZADO POR', pero el proceso exige dos
    autorizantes: se reparte ese recuadro en dos mitades."""
    c = ov.c
    autorizaciones = solicitud.get('autorizaciones', [])

    # Solicitante
    x0, y0, x1, y1 = CAJA_SOLICITANTE
    if solicitud.get('solicitado_por'):
        c.setFont('Helvetica-Bold', 9)
        c.drawCentredString((x0 + x1) / 2, y0 + 24, str(solicitud['solicitado_por']))

    # Autorizantes: mitad izquierda y mitad derecha del recuadro original
    ax0, ay0, ax1, ay1 = CAJA_AUTORIZANTES
    medio = (ax0 + ax1) / 2

    c.setStrokeColor(GRIS)
    c.setLineWidth(0.4)
    c.setDash(1, 2)
    c.line(medio, ay0 + 3, medio, ay1 - 3)
    c.setDash()

    mitades = [(ax0, medio), (medio, ax1)]
    for i, (mx0, mx1) in enumerate(mitades):
        centro = (mx0 + mx1) / 2
        if i < len(autorizaciones):
            a = autorizaciones[i]
            c.setFillColor(black)
            c.setFont('Helvetica-Bold', 7.5)
            c.drawCentredString(centro, ay0 + 31, ov._recortar(
                a.get('nombre', ''), mx1 - mx0 - 6, 'Helvetica-Bold', 7.5))
            c.setFont('Helvetica', 5)
            c.drawCentredString(centro, ay0 + 23, ov._recortar(
                a.get('cargo', ''), mx1 - mx0 - 6, 'Helvetica', 5))
            c.setFont('Helvetica-Oblique', 4.6)
            c.drawCentredString(centro, ay0 + 15,
                                f'Autorizado digitalmente · {fmt_fecha_hora(a.get("fecha"))}')
            if a.get('excedio_tope'):
                c.setFillColor(ROJO)
                c.setFont('Helvetica-Bold', 4.2)
                c.drawCentredString(centro, ay0 + 8,
                                    f'Excede su tope de $ {fmt_money(a.get("monto_tope"))}')
                c.setFillColor(black)
        else:
            c.setFillColor(GRIS)
            c.setFont('Helvetica-Oblique', 5.5)
            c.drawCentredString(centro, ay0 + 22, 'Pendiente de autorización')
            c.setFillColor(black)


def _pie(ov, solicitud):
    """Nota al pie con el estado y la trazabilidad. Fuera del marco del formulario."""
    c = ov.c
    estado = 'AUTORIZADA' if solicitud.get('estado') == 'autorizada' else 'PENDIENTE DE AUTORIZACIÓN'
    factura = f' · Factura {solicitud["factura_numero"]}' if solicitud.get('factura_numero') else ''
    c.setFillColor(GRIS)
    c.setFont('Helvetica', 5)
    c.drawString(46, 33, f'Solicitud #{solicitud.get("id", "")} · {estado}{factura} · '
                         f'Generado por el sistema de Autorizaciones de Compra')
    c.setFillColor(black)


def _casilleros_marcados(solicitud):
    """Nombres de los casilleros que van tildados segun la solicitud."""
    marcados = set()

    def marcar(mapa, clave):
        if clave in mapa:
            marcados.add(mapa[clave])

    marcar(EMPRESAS, solicitud.get('empresa'))
    marcar(MARCAS, solicitud.get('marca'))
    marcar(PROVEEDOR_TIPO, solicitud.get('proveedor_tipo'))
    marcar(TIPO_ORDEN, solicitud.get('tipo_orden'))
    marcar(CONCEPTOS, solicitud.get('concepto'))
    marcar(FORMA_PAGO, solicitud.get('forma_pago'))
    marcar(CONDICION_PAGO, solicitud.get('condicion_pago'))

    if solicitud.get('condicion_pago') == 'cuenta_corriente':
        dias = str(solicitud.get('condicion_dias') or '')
        if dias in CONDICION_DIAS:
            marcados.add(CONDICION_DIAS[dias])
        elif dias:
            marcados.add(CONDICION_DIAS_OTRO)
    return marcados


# Todos los casilleros del formulario, en el orden en que aparecen.
TODOS_LOS_CASILLEROS = (
    list(EMPRESAS.values()) + list(MARCAS.values()) + list(PROVEEDOR_TIPO.values())
    + list(TIPO_ORDEN.values()) + list(CONCEPTOS.values()) + list(FORMA_PAGO.values())
    + list(CONDICION_PAGO.values()) + list(CONDICION_DIAS.values()) + [CONDICION_DIAS_OTRO]
)


def _completar_overlay(solicitud):
    ov = _Overlay()

    # Los casilleros se redibujan todos (marcados y sin marcar), porque el original
    # los aporta desde los campos interactivos que aca se aplanan.
    marcados = _casilleros_marcados(solicitud)
    for nombre in TODOS_LOS_CASILLEROS:
        ov.casilla(nombre, nombre in marcados)

    ov.campo(CAMPO_FECHA, solicitud.get('fecha'), bold=True)

    if solicitud.get('marca') == 'OTRO':
        ov.campo(CAMPO_MARCA_OTRO, solicitud.get('marca_otro'))

    ov.campo(CAMPO_PROVEEDOR, solicitud.get('proveedor_nombre'), bold=True)
    ov.campo(CAMPO_CUIT, solicitud.get('cuit'), bold=True)

    if solicitud.get('tipo_orden') == 'abierta':
        ov.texto_en(ZONA_DURACION_ORDEN, solicitud.get('duracion_orden'), size=7)

    if solicitud.get('concepto') == 'otros':
        ov.texto_en(ZONA_CONCEPTO_OTRO, solicitud.get('concepto_otro'), size=7)

    for i, (f_desc, f_precio, f_cant, f_total) in enumerate(FILAS_ITEMS):
        items = solicitud.get('items', [])
        if i >= len(items):
            break
        item = items[i]
        ov.campo(f_desc, item.get('descripcion'), size=7)
        ov.campo(f_precio, fmt_money(item.get('precio')), size=7, alinear='der')
        ov.campo(f_cant, fmt_cant(item.get('cantidad')), size=7, alinear='centro')
        ov.campo(f_total, fmt_money(item.get('total')), size=7, alinear='der')

    ov.campo(CAMPO_MONTO_FINAL, '$ ' + fmt_money(solicitud.get('monto_total')), bold=True)
    ov.campo(CAMPO_CBU, solicitud.get('cbu'), size=7.5)

    condicion = solicitud.get('condicion_pago')
    if condicion == 'cuenta_corriente':
        dias = str(solicitud.get('condicion_dias') or '')
        if dias and dias not in CONDICION_DIAS:
            ov.campo(CAMPO_DIAS_OTRO, dias, size=7, alinear='centro')
    if condicion == 'otras':
        ov.texto_en(ZONA_CONDICION_OTRAS, solicitud.get('condicion_otras'), size=6.5)

    ov.campo(CAMPO_CONTACTO, solicitud.get('contacto_nombre'))
    ov.campo(CAMPO_TELEFONO, solicitud.get('contacto_telefono'))
    ov.campo(CAMPO_MAIL, solicitud.get('contacto_mail'))
    ov.campo(CAMPO_OBSERVACIONES, solicitud.get('observaciones'), size=7)

    _firmas(ov, solicitud)
    _pie(ov, solicitud)
    return ov.guardar()


def generar_pdf(solicitud, destino):
    """Escribe el formulario oficial completado y aplanado en `destino`."""
    plantilla = PdfReader(PLANTILLA)
    pagina = plantilla.pages[0]

    overlay = PdfReader(_completar_overlay(solicitud))
    pagina.merge_page(overlay.pages[0])

    # Aplanar: sin campos editables, el documento firmado queda fijo.
    if '/Annots' in pagina:
        del pagina['/Annots']

    writer = PdfWriter()
    writer.add_page(pagina)
    if '/AcroForm' in writer._root_object:
        del writer._root_object['/AcroForm']
    writer.add_metadata({
        '/Title': f'Autorizacion Generica de Compra #{solicitud.get("id", "")}',
        '/Producer': 'Sistema de Autorizaciones de Compra',
    })

    with open(destino, 'wb') as fh:
        writer.write(fh)
    return destino


def excede_items(solicitud):
    """El formulario tiene 6 renglones; avisa si la factura trae mas."""
    return max(0, len(solicitud.get('items', [])) - MAX_ITEMS)
