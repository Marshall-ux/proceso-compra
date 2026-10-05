"""Tests del camino ARCA del extractor de facturas.

Correr desde server/:  python -m unittest discover tests
"""

import os
import tempfile
import unittest
from unittest import mock

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from services import extractor

DOCS = os.path.join(os.path.dirname(__file__), '..', '..', 'docs')


def _factura_arca(path, renglones, total):
    """Arma un PDF con la estructura de una factura A de ARCA."""
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont('Helvetica', 9)
    y = 800
    for linea in (
        'ORIGINAL',
        'PROVEEDOR DE PRUEBA S R L A FACTURA',
        'Punto de Venta: 00002 Comp. Nro: 00000123',
        'Razon Social: PROVEEDOR DE PRUEBA S R L Fecha de Emision: 01/09/2026',
        'Domicilio Comercial: Calle 123 - Rosario CUIT: 30548000382',
        'CUIT: 30612502354 Apellido y Nombre / Razon Social: ALCO ROSARIO S A',
        'Condicion de venta: Cuenta Corriente Remito: 00002-00025461',
        'Codigo Producto / Servicio Cantidad U. medida Precio Unit. % Bonif Subtotal Alicuota IVA Subtotal c/IVA',
    ):
        c.drawString(40, y, linea)
        y -= 14
    y -= 6
    for renglon in renglones:
        c.drawString(40, y, renglon)
        y -= 14
    y -= 120
    c.drawString(300, y, f'Importe Total: $ {total}')
    c.drawString(300, y - 14, 'CAE N°: 86350195345842')
    c.drawString(300, y - 28, 'Comprobante Autorizado')
    c.save()


class ExtractorArcaTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _extraer(self, renglones, total):
        path = os.path.join(self.tmp.name, 'factura.pdf')
        _factura_arca(path, renglones, total)
        return path, extractor.extraer_datos_factura(path)

    def test_iva_mixto_cuadra(self):
        path, r = self._extraer([
            '001 Servicio de traslado 1,00 unidades 1000,00 0,00 1000,00 21% 1210,00',
            '002 Repuesto de prueba 2,00 unidades 500,00 0,00 1000,00 10,5% 1105,00',
        ], '2315,00')

        self.assertEqual(r['items'], [
            {'descripcion': 'Servicio de traslado', 'cantidad': 1.0, 'precio': 1000.0, 'total': 1000.0},
            {'descripcion': 'Repuesto de prueba', 'cantidad': 2.0, 'precio': 500.0, 'total': 1000.0},
        ])
        # `datos` sale igual que con la extraccion generica (sin camino ARCA).
        with mock.patch.object(extractor, '_es_arca', return_value=False):
            generico = extractor.extraer_datos_factura(path)
        self.assertEqual(r['datos'], generico['datos'])

    def test_renglon_sin_leer_no_cuadra(self):
        _, r = self._extraer([
            '001 Servicio de traslado 1,00 unidades 1000,00 0,00 1000,00 21% 1210,00',
            '002 Repuesto ilegible ### ilegible',
        ], '2315,00')

        self.assertEqual(r['items'], [])

    def test_factura_no_arca_sin_cambios(self):
        r = extractor.extraer_datos_factura(os.path.join(DOCS, 'FAA 0003-00006906.pdf'))

        # Salida del extractor antes del camino ARCA.
        self.assertEqual(r, {
            'ok': True,
            'error': '',
            'datos': {
                'fecha': '01/06/2026',
                'empresa': 'NEOSTAR S.A.',
                'proveedor_nombre': 'Daniel Omar Oriti',
                'cuit': '20-12522001-1',
                'monto_total': 33093.5,
                'factura_numero': '0003-00006906',
                'condicion_pago': 'cuenta_corriente',
                'condicion_dias': '7',
                'contacto_mail': 'genesisenlinea@gmail.com',
                'contacto_telefono': '341 6840400',
                'cbu': '',
            },
            'items': [
                {'descripcion': 'TARJETA A5 IMP FRENTE 250GRS', 'cantidad': 75.0, 'precio': 364.67, 'total': 27350.0},
                {'descripcion': 'SOLICITO: IRINI', 'cantidad': 1.0, 'precio': 0.0, 'total': 0.0},
            ],
            'faltantes': ['marca', 'concepto', 'proveedor_tipo', 'tipo_orden', 'solicitado_por'],
        })


if __name__ == '__main__':
    unittest.main()
