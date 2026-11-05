"""Tests del firmante unico (solo el elegido recibe el mail y solo el puede firmar),
de la cajera por ubicacion y del recuadro de firmas del PDF.

Correr desde server/:  python -m unittest discover tests

La base temporal y la API de prueba estan en tests/apoyo.py.
"""

import os
import unittest
from unittest import mock

import pdfplumber

from services import avisos
from services import solicitudes as svc
from services.pdf_fill import generar_pdf
from tests.apoyo import PIN, ConApi, ConBase, sin_env_cajas


class CajeraPorUbicacion(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, sin_env_cajas(), clear=True)
        p.start()
        self.addCleanup(p.stop)

    def cajeras(self, ubicacion, *empresas):
        return avisos.destinatarios_cajeras({'ubicacion': ubicacion, 'empresas': list(empresas)})

    def test_listado_de_administracion(self):
        casos = [
            ('santa_fe', 'HIKARI S.A.', 'dmorelli@neostar.com.ar'),
            ('rosario', 'HIKARI S.A.', 'bcoll@neostar.com.ar'),
            ('santa_fe', 'NEOSTAR S.A.', 'evanlesberg@neostar.com.ar'),
            ('rosario', 'NEOSTAR S.A.', 'mspurello@neostar.com.ar'),
            ('rosario', 'ALCO ROSARIO S.A.', 'nblois@neostar.com.ar'),
            ('santa_fe', 'ALCO ROSARIO S.A.', 'mgonzalez@neostar.com.ar'),
        ]
        for ubicacion, empresa, mail in casos:
            with self.subTest(ubicacion=ubicacion, empresa=empresa):
                self.assertEqual(self.cajeras(ubicacion, empresa), [mail])

    def test_varias_empresas_una_cajera_por_cada_una(self):
        self.assertEqual(self.cajeras('santa_fe', 'NEOSTAR S.A.', 'ALCO ROSARIO S.A.'),
                         ['evanlesberg@neostar.com.ar', 'mgonzalez@neostar.com.ar'])

    def test_empresa_sin_cajera_por_sede_usa_la_de_la_razon_social(self):
        self.assertEqual(self.cajeras('santa_fe', 'XINOXIA S.A.'), ['mlhenning@neostar.com.ar'])
        self.assertEqual(self.cajeras('santa_fe', 'DASEOS S.A.'), ['mspurello@neostar.com.ar'])

    def test_solicitud_vieja_sin_ubicacion_avisa_como_antes(self):
        self.assertEqual(self.cajeras('', 'HIKARI S.A.'), ['bcoll@neostar.com.ar'])
        self.assertEqual(self.cajeras(None, 'ALCO ROSARIO S.A.'), ['nblois@neostar.com.ar'])

    def test_env_var_por_sede_pisa_el_default(self):
        with mock.patch.dict(os.environ, {'CAJA_SANTA_FE_HIKARI': 'otra@neostar.com.ar'}):
            self.assertEqual(self.cajeras('santa_fe', 'HIKARI S.A.'), ['otra@neostar.com.ar'])
            # La otra sede no se toca.
            self.assertEqual(self.cajeras('rosario', 'HIKARI S.A.'), ['bcoll@neostar.com.ar'])

    def test_env_var_vacia_es_no_avisar(self):
        with mock.patch.dict(os.environ, {'CAJA_SANTA_FE_HIKARI': ''}):
            self.assertEqual(self.cajeras('santa_fe', 'HIKARI S.A.'), [])


class ValidarUbicacion(unittest.TestCase):
    def errores_de_ubicacion(self, ubicacion):
        return [e for e in svc.validar({'ubicacion': ubicacion}) if 'bicación' in e]

    def test_es_obligatoria(self):
        self.assertEqual(self.errores_de_ubicacion(''), ['Elegí la ubicación (Rosario o Santa Fe)'])

    def test_solo_rosario_o_santa_fe(self):
        self.assertEqual(self.errores_de_ubicacion('cordoba'), ['Ubicación inválida'])
        self.assertEqual(self.errores_de_ubicacion('rosario'), [])
        self.assertEqual(self.errores_de_ubicacion('santa_fe'), [])


class FirmanteUnico(ConBase):
    def test_hay_que_elegir_uno(self):
        ids, errores = svc.validar_avisar_a(self.datos(avisar_a=[]))
        self.assertEqual(ids, [])
        self.assertEqual(len(errores), 1)

    def test_no_se_puede_elegir_mas_de_uno(self):
        _, errores = svc.validar_avisar_a(self.datos(avisar_a=[self.uno, self.otro]))
        self.assertEqual(errores, ['Elegí un solo firmante: el aviso le llega solo a esa persona'])

    def test_uno_solo_es_valido(self):
        self.assertEqual(svc.validar_avisar_a(self.datos()), ([self.uno], []))

    def test_el_aviso_va_solo_al_elegido_sin_copia_fija(self):
        # La copia fija de antes ya no existe: aunque la variable siga en un .env viejo,
        # no se le manda nada.
        with mock.patch.dict(os.environ, {'AUTORIZA_NOTIF_EMAIL': 'copia@neostar.com.ar'}):
            destinos = avisos.destinatarios_autorizantes({'avisar_a': [self.uno]})
        self.assertEqual(destinos, [self.mail_uno])


class CircuitoCompleto(ConApi):
    """Alta por la API -> mail solo al firmante; firma -> mail a la cajera de la sede."""

    def test_alta_y_firma(self):
        r = self.api.post('/api/solicitudes', json=self.datos())
        self.assertEqual(r.status_code, 201, r.get_json())
        solicitud = r.get_json()
        self.assertEqual(solicitud['ubicacion'], 'santa_fe')
        self.assertEqual(self.mails, [self.mail_uno])

        self.mails.clear()
        r = self.api.post(f'/api/solicitudes/{solicitud["id"]}/autorizar',
                          json={'autorizado_id': self.uno, 'pin': PIN})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['estado'], 'autorizada')
        # Santa Fe + HIKARI
        self.assertEqual(self.mails, ['dmorelli@neostar.com.ar'])

    def test_alta_con_dos_firmantes_se_rechaza(self):
        r = self.api.post('/api/solicitudes', json=self.datos(avisar_a=[self.uno, self.otro]))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.mails, [])

    def test_alta_sin_ubicacion_se_rechaza(self):
        r = self.api.post('/api/solicitudes', json=self.datos(ubicacion=''))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Elegí la ubicación (Rosario o Santa Fe)', r.get_json()['errores'])


class SoloFirmaElElegido(ConApi):
    def test_otro_habilitado_no_puede_firmar(self):
        sid = self.alta()
        r = self.firmar(sid, self.otro)
        self.assertEqual(r.status_code, 400)
        self.assertIn('no puede firmarla', r.get_json()['error'])
        self.assertEqual(svc.obtener(sid)['autorizaciones'], [])

        self.assertEqual(self.firmar(sid, self.uno).get_json()['estado'], 'autorizada')

    def test_en_lote_se_saltea_si_no_es_el_elegido(self):
        sid = self.alta()
        r = self.api.post('/api/solicitudes/autorizar-lote',
                          json={'autorizado_id': self.otro, 'pin': PIN, 'ids': [sid]})
        self.assertEqual(r.get_json()['firmadas'], [])
        self.assertEqual(r.get_json()['salteadas'][0]['id'], sid)

    def test_para_firmar_solo_le_aparece_al_elegido(self):
        sid = self.alta()
        self.assertIn(sid, [s['id'] for s in svc.para_firmar(self.uno)])
        self.assertNotIn(sid, [s['id'] for s in svc.para_firmar(self.otro)])

    def test_el_detalle_marca_quien_puede_firmar(self):
        sid = self.alta()
        disponibles = {a['id']: a for a in svc.autorizados_para(svc.obtener(sid))}
        self.assertTrue(disponibles[self.uno]['puede_firmar'])
        self.assertFalse(disponibles[self.otro]['puede_firmar'])

    def test_vieja_sin_firmante_la_firma_cualquier_habilitado(self):
        sid = self.alta()
        self.fijar_avisar_a(sid, '')
        self.assertIn(sid, [s['id'] for s in svc.para_firmar(self.otro)])
        self.assertEqual(self.firmar(sid, self.otro).get_json()['estado'], 'autorizada')

    def test_editar_cambia_el_firmante_y_le_avisa_al_nuevo(self):
        sid = self.alta()
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(avisar_a=[self.otro]))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.mails, [self.mail_otro])
        self.assertEqual(self.firmar(sid, self.uno).status_code, 400)
        self.assertEqual(self.firmar(sid, self.otro).get_json()['estado'], 'autorizada')

    def test_editar_sin_cambiar_firmante_no_reenvia_el_mail(self):
        sid = self.alta()
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(proveedor_nombre='Otro Nombre'))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.mails, [])

    def test_editar_vieja_con_varios_quedandose_con_uno_no_reenvia(self):
        sid = self.alta()
        self.fijar_avisar_a(sid, f'[{self.uno}, {self.otro}]')
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(avisar_a=[self.otro]))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.mails, [])

    def test_editar_sin_firmante_se_rechaza(self):
        sid = self.alta()
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(avisar_a=[]))
        self.assertEqual(r.status_code, 400)


class UnaSolaFirma(ConApi):
    """Con firmante elegido no hay segunda firma: la suya la autoriza, y si su tope ya
    no cubre el monto no firma (se destraba eligiendo otro firmante)."""

    def test_la_firma_del_elegido_la_autoriza_sola(self):
        r = self.firmar(self.alta(), self.uno).get_json()
        self.assertEqual(r['estado'], 'autorizada')
        self.assertEqual(len(r['autorizaciones']), 1)
        self.assertFalse(r['requiere_segunda_firma'])

    def test_elegido_que_ya_no_cubre_el_monto_no_firma(self):
        sid = self.alta()
        self.fijar_tope(self.uno, 500)
        r = self.firmar(sid, self.uno)
        self.assertEqual(r.status_code, 400)
        self.assertIn('supera el tope', r.get_json()['error'])
        s = svc.obtener(sid)
        self.assertEqual((s['estado'], s['autorizaciones']), ('pendiente', []))
        self.assertFalse(s['requiere_segunda_firma'])

        # Se destraba editando y eligiendo otro firmante, que la firma solo.
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(avisar_a=[self.otro]))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.firmar(sid, self.otro).get_json()['estado'], 'autorizada')

    def test_para_firmar_no_le_lista_lo_que_ya_no_puede_firmar(self):
        sid = self.alta()
        self.assertIn(sid, [s['id'] for s in svc.para_firmar(self.uno)])
        self.fijar_tope(self.uno, 500)
        self.assertNotIn(sid, [s['id'] for s in svc.para_firmar(self.uno)])

    def test_en_lote_tampoco_firma_sin_cubrir_el_monto(self):
        sid = self.alta()
        self.fijar_tope(self.uno, 500)
        r = self.api.post('/api/solicitudes/autorizar-lote',
                          json={'autorizado_id': self.uno, 'pin': PIN, 'ids': [sid]}).get_json()
        self.assertEqual(r['firmadas'], [])
        self.assertIn('supera el tope', r['salteadas'][0]['motivo'])

    def test_vieja_sin_firmante_sigue_con_segunda_firma(self):
        sid = self.alta()
        self.fijar_avisar_a(sid, '')
        self.fijar_tope(self.otro, 500)
        r = self.firmar(sid, self.otro).get_json()
        self.assertEqual(r['estado'], 'pendiente')
        self.assertTrue(r['requiere_segunda_firma'])
        pendiente = {s['id']: s for s in svc.para_firmar(self.uno)}[sid]
        self.assertTrue(pendiente['requiere_segunda_firma'])
        self.assertEqual(self.firmar(sid, self.uno).get_json()['estado'], 'autorizada')


class RecuadroDeFirmasDelPdf(ConApi):
    """Recuadro AUTORIZADO POR del F 8.4-01: una autorizada nunca dice "Pendiente de
    autorización", y la mitad para una segunda firma aparece solo si hace falta."""

    def texto_pdf(self, sid):
        destino = os.path.join(self.dir, f'agc-{sid}.pdf')
        generar_pdf(svc.obtener(sid), destino)
        with pdfplumber.open(destino) as pdf:
            return pdf.pages[0].extract_text()

    def test_autorizada_con_una_firma_no_dice_pendiente(self):
        sid = self.alta()
        self.assertEqual(self.firmar(sid, self.uno).get_json()['estado'], 'autorizada')
        texto = self.texto_pdf(sid)
        self.assertEqual(texto.count('Autorizado digitalmente'), 1)
        self.assertNotIn('Pendiente de autorizaci', texto)

    def test_pendiente_sin_firmas_lo_dice_una_sola_vez(self):
        sid = self.alta()
        self.assertEqual(self.texto_pdf(sid).count('Pendiente de autorizaci'), 1)

    def test_vieja_con_una_firma_esperando_la_segunda(self):
        # Vieja sin firmante elegido: firma alguien cuyo tope no cubre el monto.
        sid = self.alta()
        self.fijar_avisar_a(sid, '')
        self.fijar_tope(self.otro, 500)
        self.assertEqual(self.firmar(sid, self.otro).get_json()['estado'], 'pendiente')
        texto = self.texto_pdf(sid)
        self.assertEqual(texto.count('Autorizado digitalmente'), 1)
        self.assertEqual(texto.count('Pendiente de autorizaci'), 1)


if __name__ == '__main__':
    unittest.main()
