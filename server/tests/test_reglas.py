"""Tests de las reglas de negocio que no cubre test_avisos: marcas, topes de las
solicitudes viejas, dólares, pagos imputados, eliminación, edición, y el PDF y el ZIP
armados en memoria.

Correr desde server/:  python -m unittest discover tests
"""

import io
import os
import unittest
import zipfile
from unittest import mock

from models import database
from services import admin
from services import solicitudes as svc
from services.marcas import listas_habilitadas
from tests.apoyo import PIN, ConApi


class ListasPorMarca(unittest.TestCase):
    def test_una_marca_su_planilla_mas_multimarca(self):
        self.assertEqual(listas_habilitadas(['NISSAN']), ['multimarca', 'nissan'])
        self.assertEqual(listas_habilitadas(['FCA']), ['jeep', 'jeep_byd', 'multimarca'])
        self.assertEqual(listas_habilitadas(['SUZUKI']), ['kia', 'multimarca'])

    def test_varias_marcas_solo_quien_las_cubre_todas(self):
        self.assertEqual(listas_habilitadas(['NISSAN', 'KIA']), ['multimarca'])
        self.assertEqual(listas_habilitadas(['BYD', 'FCA']), ['jeep_byd', 'multimarca'])

    def test_sin_planilla_propia_solo_multimarca(self):
        self.assertEqual(listas_habilitadas([]), ['multimarca'])
        self.assertEqual(listas_habilitadas(['OTRO']), ['multimarca'])


class ClavesDeEjemplo(unittest.TestCase):
    def test_la_del_compose_y_la_del_codigo_cuentan_como_de_ejemplo(self):
        for clave, de_ejemplo in (('cambiar-esta-clave', True), ('neostar-admin', True),
                                  ('una-propia', False)):
            with self.subTest(clave=clave), mock.patch.dict(os.environ, {'ADMIN_PASSWORD': clave}):
                self.assertEqual(admin.usando_default(), de_ejemplo)
        sin_clave = {k: v for k, v in os.environ.items() if k != 'ADMIN_PASSWORD'}
        with mock.patch.dict(os.environ, sin_clave, clear=True):
            self.assertTrue(admin.usando_default())


class ConVieja(ConApi):
    """Solicitud cargada antes del firmante elegido: la firma cualquier habilitado."""

    def vieja(self, **cambios):
        sid = self.alta(**cambios)
        self.fijar_avisar_a(sid, '')
        return sid

    def de_planilla(self, lista):
        conn = database.get_db()
        try:
            return conn.execute('SELECT id FROM autorizados WHERE activo = 1 AND lista = ? '
                                'ORDER BY id LIMIT 1', (lista,)).fetchone()['id']
        finally:
            conn.close()


class FirmaPorMarcaYTope(ConVieja):
    def test_no_firma_quien_no_esta_habilitado_para_la_marca(self):
        sid = self.vieja(marcas=['KIA'])
        r = self.firmar(sid, self.de_planilla('nissan'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('no está habilitado', r.get_json()['error'])

    def test_una_firma_dentro_del_tope_alcanza(self):
        sid = self.vieja()
        self.fijar_tope(self.otro, 5000)
        r = self.firmar(sid, self.otro).get_json()
        self.assertEqual((r['estado'], len(r['autorizaciones'])), ('autorizada', 1))

    def test_dos_firmas_que_exceden_su_tope_la_autorizan_y_queda_registrado(self):
        # Regla vigente en las viejas: el tope no frena la segunda firma, queda marcado.
        sid = self.vieja()
        self.fijar_tope(self.uno, 500)
        self.fijar_tope(self.otro, 500)
        self.assertEqual(self.firmar(sid, self.otro).get_json()['estado'], 'pendiente')
        r = self.firmar(sid, self.uno).get_json()
        self.assertEqual(r['estado'], 'autorizada')
        self.assertEqual([a['excedio_tope'] for a in r['autorizaciones']], [1, 1])

    def test_la_misma_persona_no_firma_dos_veces(self):
        sid = self.vieja()
        self.fijar_tope(self.otro, 500)
        self.firmar(sid, self.otro)
        r = self.firmar(sid, self.otro)
        self.assertEqual(r.status_code, 400)
        self.assertIn('ya autorizó', r.get_json()['error'])

    def test_editar_borra_las_firmas(self):
        sid = self.vieja()
        self.fijar_tope(self.otro, 500)
        self.firmar(sid, self.otro)
        self.assertEqual(len(svc.obtener(sid)['autorizaciones']), 1)
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(proveedor_nombre='Otro SA'))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['autorizaciones'], [])

    def test_una_autorizada_no_se_edita(self):
        sid = self.alta()
        self.firmar(sid, self.uno)
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(proveedor_nombre='Otro SA'))
        self.assertEqual(r.status_code, 400)


class EnDolares(ConApi):
    def test_sin_tipo_de_cambio_no_se_carga(self):
        r = self.api.post('/api/solicitudes', json=self.datos(moneda='USD', monto_total=1000))
        self.assertEqual(r.status_code, 400)
        self.assertTrue(any('tipo de cambio' in e for e in r.get_json()['errores']))

    def test_el_tope_se_compara_en_pesos(self):
        # U$S 1.000 a 1.000 = $ 1.000.000: con tope de $ 500.000 no puede ser firmante.
        self.fijar_tope(self.otro, 500_000)
        usd = dict(moneda='USD', monto_total=1000, tipo_cambio=1000)
        ids = [c['id'] for c in svc.candidatos_aviso(['NISSAN'], 1_000_000)]
        self.assertNotIn(self.otro, ids)
        self.assertIn(self.uno, ids)
        r = self.api.post('/api/solicitudes', json=self.datos(avisar_a=[self.otro], **usd))
        self.assertEqual(r.status_code, 400)

        sid = self.alta(**usd)
        self.assertEqual(svc.obtener(sid)['monto_pesos'], 1_000_000)
        self.assertEqual(self.firmar(sid, self.uno).get_json()['estado'], 'autorizada')

    def test_en_pesos_no_queda_un_tipo_de_cambio_viejo(self):
        sid = self.alta(moneda='ARS', tipo_cambio=1000)
        self.assertEqual(svc.obtener(sid)['tipo_cambio'], 0)


class PagosImputados(ConApi):
    def autorizada(self, **cambios):
        sid = self.alta(**cambios)
        self.assertEqual(self.firmar(sid, self.uno).get_json()['estado'], 'autorizada')
        return sid

    def pago(self, sid, monto, **extra):
        return self.api.post(f'/api/solicitudes/{sid}/pagos',
                             json={'descripcion': 'avance', 'monto': monto, 'facturas': [], **extra})

    def firmar_pago(self, sid, pid, quien):
        return self.api.post(f'/api/solicitudes/{sid}/pagos/{pid}/firmar',
                             json={'autorizado_id': quien, 'pin': PIN})

    def test_solo_en_una_agc_autorizada(self):
        r = self.pago(self.alta(), 300)
        self.assertEqual(r.status_code, 400)

    def test_lo_firma_cualquier_habilitado_no_solo_el_firmante_de_la_agc(self):
        sid = self.autorizada()
        pid = self.pago(sid, 300).get_json()['pagos'][0]['id']
        r = self.firmar_pago(sid, pid, self.otro).get_json()
        self.assertEqual(r['pagos'][0]['estado'], 'conforme')

    def test_si_supera_el_tope_hace_falta_una_segunda_firma(self):
        sid = self.autorizada()
        pid = self.pago(sid, 300).get_json()['pagos'][0]['id']
        self.fijar_tope(self.otro, 100)
        r = self.firmar_pago(sid, pid, self.otro).get_json()
        self.assertEqual(r['pagos'][0]['estado'], 'pendiente')
        self.assertTrue(r['pagos'][0]['requiere_segunda_firma'])
        self.assertTrue(r['aviso_tope'])
        self.assertEqual(self.firmar_pago(sid, pid, self.uno).get_json()['pagos'][0]['estado'],
                         'conforme')

    def test_un_pago_conforme_no_se_elimina_y_uno_pendiente_si(self):
        sid = self.autorizada()
        conforme = self.pago(sid, 300).get_json()['pagos'][0]['id']
        self.firmar_pago(sid, conforme, self.otro)
        pendiente = self.pago(sid, 200).get_json()['pagos'][1]['id']
        self.assertEqual(self.api.delete(f'/api/solicitudes/{sid}/pagos/{conforme}').status_code, 400)
        r = self.api.delete(f'/api/solicitudes/{sid}/pagos/{pendiente}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p['id'] for p in r.get_json()['pagos']], [conforme])

    def test_resumen_avisa_si_una_cerrada_se_pasa_del_presupuesto(self):
        sid = self.autorizada()
        self.pago(sid, 700)
        r = self.pago(sid, 500).get_json()['pagos_resumen']
        self.assertEqual((r['imputado'], r['saldo'], r['excede']), (1200, -200, True))

    def test_en_una_abierta_superar_el_monto_no_es_exceso(self):
        sid = self.autorizada(tipo_orden='abierta', duracion_orden='6 meses')
        r = self.pago(sid, 1500).get_json()['pagos_resumen']
        self.assertFalse(r['excede'])

    def test_en_dolares_cada_pago_lleva_su_tipo_de_cambio(self):
        sid = self.autorizada(moneda='USD', monto_total=1000, tipo_cambio=1000)
        self.assertEqual(self.pago(sid, 300).status_code, 400)
        self.assertEqual(self.pago(sid, 300, tipo_cambio=1100).status_code, 201)


class Eliminacion(ConApi):
    def eliminar(self, sid, motivo='cargada por error', clave=None):
        headers = {'X-Admin-Password': clave} if clave else {}
        return self.api.delete(f'/api/solicitudes/{sid}', headers=headers,
                               json={'motivo': motivo, 'eliminado_por': 'Quien Borra'})

    def test_sin_motivo_no_se_elimina(self):
        self.assertEqual(self.eliminar(self.alta(), motivo='  ').status_code, 400)

    def test_queda_el_acta_con_el_motivo(self):
        sid = self.alta()
        self.assertEqual(self.eliminar(sid).status_code, 200)
        self.assertEqual(self.api.get(f'/api/solicitudes/{sid}').status_code, 404)
        acta = self.api.get('/api/eliminaciones').get_json()[0]
        self.assertEqual((acta['solicitud_id'], acta['motivo'], acta['eliminado_por']),
                         (sid, 'cargada por error', 'Quien Borra'))

    def test_una_autorizada_solo_con_la_clave_de_administracion(self):
        sid = self.alta()
        self.firmar(sid, self.uno)
        with mock.patch.dict(os.environ, {'ADMIN_PASSWORD': 'clave-de-prueba'}):
            self.assertEqual(self.eliminar(sid).status_code, 403)
            self.assertEqual(self.eliminar(sid, clave='otra').status_code, 403)
            self.assertEqual(self.eliminar(sid, clave='clave-de-prueba').status_code, 200)


class ListaDelInicio(ConApi):
    def test_dice_a_quien_espera_y_quien_firmo(self):
        sid = self.alta()
        elegido = svc.obtener(sid)['avisados'][0]
        fila = {s['id']: s for s in self.api.get('/api/solicitudes').get_json()}[sid]
        self.assertEqual((fila['firmante'], fila['firmado_por']), (elegido, None))

        self.firmar(sid, self.uno)
        fila = {s['id']: s for s in self.api.get('/api/solicitudes').get_json()}[sid]
        self.assertEqual(fila['firmado_por'], elegido)

    def test_una_vieja_sin_firmante_no_espera_a_nadie_en_particular(self):
        sid = self.alta()
        self.fijar_avisar_a(sid, '')
        fila = {s['id']: s for s in self.api.get('/api/solicitudes').get_json()}[sid]
        self.assertEqual(fila['firmante'], '')


class PdfYZipEnMemoria(ConApi):
    def test_pdf(self):
        r = self.api.get(f'/api/solicitudes/{self.alta()}/pdf')
        self.assertEqual((r.status_code, r.mimetype), (200, 'application/pdf'))
        self.assertTrue(r.data.startswith(b'%PDF'))

    def test_pdf_con_facturas(self):
        r = self.api.get(f'/api/solicitudes/{self.alta()}/pdf-completo')
        self.assertEqual((r.status_code, r.mimetype), (200, 'application/pdf'))
        self.assertTrue(r.data.startswith(b'%PDF'))

    def test_zip_de_una_y_de_varias(self):
        uno, dos = self.alta(), self.alta()
        nombres = zipfile.ZipFile(io.BytesIO(self.api.get(f'/api/solicitudes/{uno}/zip').data)).namelist()
        self.assertIn(f'Autorizacion-{uno:04d}.pdf', nombres)
        self.assertIn('resumen.txt', nombres)

        r = self.api.get(f'/api/solicitudes/zip?ids={uno},{dos}')
        pdfs = [n for n in zipfile.ZipFile(io.BytesIO(r.data)).namelist() if n.endswith('.pdf')]
        self.assertEqual(len(pdfs), 2)


if __name__ == '__main__':
    unittest.main()
