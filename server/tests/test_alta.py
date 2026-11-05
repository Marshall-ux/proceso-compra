"""Tests del alta: errores por campo, CUIT, legajo, fecha y proveedor por CUIT.

Correr desde server/:  python -m unittest discover tests
"""

import unittest

from services import solicitudes as svc
from tests.apoyo import ConApi


class ValidacionDelAlta(ConApi):
    def campos_con_error(self, **cambios):
        r = self.api.post('/api/solicitudes', json=self.datos(**cambios))
        self.assertEqual(r.status_code, 400, r.get_json())
        return r.get_json()['campos']

    def test_el_cuit_es_obligatorio(self):
        self.assertIn('Falta el CUIT', self.campos_con_error(cuit='')['cuit'])

    def test_un_cuit_mal_tipeado_no_pasa(self):
        self.assertIn('no es válido', self.campos_con_error(cuit='30-71234567-8')['cuit'])

    def test_el_cuit_se_guarda_con_guiones(self):
        sid = self.alta(cuit='30712345671')
        self.assertEqual(svc.obtener(sid)['cuit'], '30-71234567-1')

    def test_un_proveedor_nuevo_necesita_el_legajo(self):
        self.assertIn('legajo', self.campos_con_error(proveedor_tipo='nuevo')['legajo_archivo'])
        self.alta(proveedor_tipo='nuevo', legajo_archivo='legajo.pdf', legajo_nombre='legajo.pdf')

    def test_la_fecha_es_dd_mm_aaaa_y_existe(self):
        self.assertIn('dd/mm/aaaa', self.campos_con_error(fecha='2026-11-05')['fecha'])
        self.assertIn('dd/mm/aaaa', self.campos_con_error(fecha='31/02/2026')['fecha'])

    def test_cada_error_va_con_su_campo_y_sin_nombres_internos(self):
        campos = self.campos_con_error(proveedor_tipo='', tipo_orden='', solicitado_por='', criticidad='')
        self.assertEqual(set(campos), {'proveedor_tipo', 'tipo_orden', 'solicitado_por', 'criticidad'})
        for mensaje in campos.values():
            self.assertNotIn('_', mensaje)

    def test_el_firmante_tambien_va_con_su_campo(self):
        self.assertIn('avisar_a', self.campos_con_error(avisar_a=[]))


class ProveedorPorCuit(ConApi):
    def buscar(self, cuit):
        return self.api.get(f'/api/proveedores/{cuit}').get_json()

    def test_sin_solicitudes_anteriores_no_lo_encuentra(self):
        self.assertEqual(self.buscar('30712345671'), {'encontrado': False})

    def test_un_cuit_incompleto_no_se_busca(self):
        self.alta()
        self.assertEqual(self.buscar('3071'), {'encontrado': False})

    def test_trae_lo_mas_reciente_de_cada_dato(self):
        self.alta(contacto_telefono='111', legajo_archivo='legajo-viejo.pdf', legajo_nombre='legajo.pdf')
        ultima = self.alta(contacto_telefono='222', proveedor_nombre='Proveedor SA (nuevo nombre)')
        r = self.buscar('30-71234567-1')
        self.assertEqual((r['encontrado'], r['solicitudes'], r['ultima_id']), (True, 2, ultima))
        self.assertEqual(r['datos']['contacto_telefono'], '222')
        self.assertEqual(r['datos']['proveedor_nombre'], 'Proveedor SA (nuevo nombre)')
        # El legajo está solo en la primera: igual lo trae, con su nombre.
        self.assertEqual((r['datos']['legajo_archivo'], r['datos']['legajo_nombre']),
                         ('legajo-viejo.pdf', 'legajo.pdf'))


if __name__ == '__main__':
    unittest.main()
