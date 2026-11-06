"""Tests de la lista del inicio: filtros, páginas y exportación a Excel.

Correr desde server/:  python -m unittest discover tests
"""

import io
import unittest
from datetime import datetime

from openpyxl import load_workbook

from models import database
from services import solicitudes as svc
from tests.apoyo import ConApi


class FiltrosYPaginas(ConApi):
    def lista(self, **params):
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        return self.api.get(f'/api/solicitudes?{qs}').get_json()

    def ids(self, **params):
        return [s['id'] for s in self.lista(**params)['solicitudes']]

    def cargada_el(self, sid, cuando):
        conn = database.get_db()
        try:
            conn.execute('UPDATE solicitudes SET created_at = ? WHERE id = ?', (cuando, sid))
            conn.commit()
        finally:
            conn.close()

    def test_de_a_una_pagina_y_las_mas_nuevas_primero(self):
        ids = [self.alta() for _ in range(5)]
        pagina = svc.listar(None, pagina=2, por_pagina=2)
        self.assertEqual([s['id'] for s in pagina['solicitudes']], [ids[2], ids[1]])
        self.assertEqual((pagina['total'], pagina['pagina']), (5, 2))
        r = self.lista()
        self.assertEqual((r['total'], r['por_pagina']), (5, svc.POR_PAGINA))

    def test_filtra_por_marca_ubicacion_y_urgencia(self):
        a = self.alta(marcas=['NISSAN'], ubicacion='rosario', criticidad='urgente')
        b = self.alta(marcas=['KIA'], ubicacion='santa_fe', criticidad='informado')
        self.assertEqual(self.ids(marca='KIA'), [b])
        self.assertEqual(self.ids(ubicacion='rosario'), [a])
        self.assertEqual(self.ids(urgente=1), [a])
        self.assertEqual(self.lista(marca='KIA')['total'], 1)

    def test_filtra_por_fecha_de_carga(self):
        a = self.alta()
        b = self.alta()
        self.cargada_el(a, '2026-10-01 10:00:00')
        self.assertEqual(self.ids(desde='2026-10-01', hasta='2026-10-31'), [a])
        self.assertEqual(self.ids(desde='2026-10-02'), [b])

    def test_una_fecha_mal_escrita_no_filtra(self):
        a, b = self.alta(), self.alta()
        self.assertEqual(self.ids(desde='ayer'), [b, a])


class ListaEnExcel(ConApi):
    def test_trae_todas_las_filtradas_con_montos_y_fechas_de_verdad(self):
        nissan = self.alta(marcas=['NISSAN'], monto_total=1500.5)
        self.alta(marcas=['KIA'])
        r = self.api.get('/api/solicitudes/excel?marca=NISSAN')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r.mimetype)
        hoja = load_workbook(io.BytesIO(r.data)).active
        titulos = [c.value for c in hoja[1]]
        self.assertEqual(hoja.max_row, 2)   # encabezado + la de NISSAN
        fila = {titulo: celda.value for titulo, celda in zip(titulos, hoja[2])}
        self.assertEqual(fila['N°'], nissan)
        self.assertEqual(fila['Monto'], 1500.5)
        self.assertIsInstance(fila['Cargada'], datetime)
        self.assertEqual(fila['Estado'], 'Pendiente')
        self.assertEqual(fila['Firmante'], svc.obtener(nissan)['avisados'][0])


if __name__ == '__main__':
    unittest.main()
