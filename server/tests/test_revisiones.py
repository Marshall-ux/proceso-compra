"""Tests de devolver para corregir y rechazar (services/revisiones.py).

Correr desde server/:  python -m unittest discover tests
"""

import os
import unittest
from unittest import mock

import pdfplumber

from services import solicitudes as svc
from services.pdf_fill import generar_pdf
from tests.apoyo import PIN, ConApi


class DevolverYRechazar(ConApi):
    def revisar(self, sid, quien, accion, motivo='falta el remito'):
        return self.api.post(f'/api/solicitudes/{sid}/revisar', json={
            'autorizado_id': quien, 'pin': PIN, 'accion': accion, 'motivo': motivo})

    def test_hace_falta_un_motivo(self):
        r = self.revisar(self.alta(), self.uno, 'observar', motivo='  ')
        self.assertEqual(r.status_code, 400)
        self.assertIn('corregir', r.get_json()['error'])

    def test_solo_el_firmante_elegido_puede_devolverla(self):
        r = self.revisar(self.alta(), self.otro, 'observar')
        self.assertEqual(r.status_code, 400)
        self.assertIn('no es el firmante', r.get_json()['error'])

    def test_una_vieja_sin_firmante_la_devuelve_cualquier_habilitado(self):
        sid = self.alta()
        self.fijar_avisar_a(sid, '')
        self.assertEqual(self.revisar(sid, self.otro, 'observar').get_json()['estado'], 'observada')

    def test_devuelta_no_se_firma_ni_aparece_para_firmar(self):
        sid = self.alta()
        r = self.revisar(sid, self.uno, 'observar').get_json()
        self.assertEqual(r['estado'], 'observada')
        self.assertEqual(r['revisiones'][-1]['motivo'], 'falta el remito')
        self.assertEqual(self.firmar(sid, self.uno).status_code, 400)
        self.assertNotIn(sid, [s['id'] for s in svc.para_firmar(self.uno)])

    def test_al_corregirla_vuelve_a_firma_y_le_avisa_al_firmante(self):
        sid = self.alta()
        self.revisar(sid, self.uno, 'observar')
        self.mails.clear()
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(proveedor_nombre='Corregido SA'))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['estado'], 'pendiente')
        self.assertEqual(self.mails, [self.mail_uno])
        self.assertEqual(self.firmar(sid, self.uno).get_json()['estado'], 'autorizada')

    def test_rechazada_es_definitiva_y_no_se_le_avisa_a_nadie(self):
        sid = self.alta()
        r = self.revisar(sid, self.uno, 'rechazar')
        self.assertEqual(r.get_json()['estado'], 'rechazada')
        self.assertEqual(self.mails, [])
        self.assertEqual(self.api.put(f'/api/solicitudes/{sid}', json=self.datos()).status_code, 400)
        self.assertIn('rechazada', self.firmar(sid, self.uno).get_json()['error'])
        self.assertEqual(self.revisar(sid, self.uno, 'observar').status_code, 400)

    def test_una_rechazada_solo_la_elimina_administracion(self):
        sid = self.alta()
        self.revisar(sid, self.uno, 'rechazar')
        with mock.patch.dict(os.environ, {'ADMIN_PASSWORD': 'clave-de-prueba'}):
            r = self.api.delete(f'/api/solicitudes/{sid}', json={'motivo': 'limpieza'})
            self.assertEqual(r.status_code, 403)
            r = self.api.delete(f'/api/solicitudes/{sid}', json={'motivo': 'limpieza'},
                                headers={'X-Admin-Password': 'clave-de-prueba'})
            self.assertEqual(r.status_code, 200)

    def test_una_devuelta_se_puede_rechazar_y_queda_el_historial(self):
        sid = self.alta()
        self.revisar(sid, self.uno, 'observar')
        r = self.revisar(sid, self.uno, 'rechazar', motivo='no corresponde').get_json()
        self.assertEqual(r['estado'], 'rechazada')
        self.assertEqual([x['accion'] for x in r['revisiones']], ['observada', 'rechazada'])

    def test_la_lista_muestra_quien_y_por_que(self):
        sid = self.alta()
        self.revisar(sid, self.uno, 'observar')
        fila = {s['id']: s for s in self.api.get('/api/solicitudes').get_json()['solicitudes']}[sid]
        self.assertEqual(fila['revision_motivo'], 'falta el remito')
        self.assertEqual(fila['revision_por'], svc.obtener(sid)['avisados'][0])

    def test_el_pdf_dice_rechazada(self):
        sid = self.alta()
        self.revisar(sid, self.uno, 'rechazar')
        destino = os.path.join(self.dir, 'rechazada.pdf')
        generar_pdf(svc.obtener(sid), destino)
        with pdfplumber.open(destino) as pdf:
            texto = pdf.pages[0].extract_text()
        self.assertIn('RECHAZADA', texto)
        self.assertNotIn('Pendiente de autorizaci', texto)


if __name__ == '__main__':
    unittest.main()
