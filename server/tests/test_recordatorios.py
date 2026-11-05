"""Tests de los recordatorios al firmante (services/recordatorios.py).

Correr desde server/:  python -m unittest discover tests
"""

import unittest
from datetime import datetime, timedelta

from models import database
from services import recordatorios
from tests.apoyo import PIN, ConApi

LUNES = datetime(2026, 11, 9, 10, 0)     # lunes, en horario
SABADO = datetime(2026, 11, 14, 10, 0)


class Recordatorios(ConApi):
    def le_toca_desde(self, sid, cuando):
        conn = database.get_db()
        try:
            conn.execute('UPDATE solicitudes SET aviso_firmante_at = ? WHERE id = ?',
                         (cuando.strftime('%Y-%m-%d %H:%M:%S'), sid))
            conn.commit()
        finally:
            conn.close()

    def columnas(self, sid, *nombres):
        conn = database.get_db()
        try:
            fila = conn.execute(f'SELECT {", ".join(nombres)} FROM solicitudes WHERE id = ?',
                                (sid,)).fetchone()
            return tuple(fila)
        finally:
            conn.close()

    def vencida(self, **cambios):
        """Pendiente cuyo plazo de 48 h ya se cumplió el LUNES."""
        sid = self.alta(**cambios)
        self.le_toca_desde(sid, LUNES - timedelta(hours=49))
        return sid

    def test_antes_de_las_48_h_no_sale(self):
        sid = self.alta()
        self.le_toca_desde(sid, LUNES - timedelta(hours=47))
        self.assertEqual(recordatorios.enviar(LUNES), 0)
        self.assertEqual(self.mails, [])

    def test_a_las_48_h_le_llega_al_firmante_una_sola_vez(self):
        self.vencida()
        self.assertEqual(recordatorios.enviar(LUNES), 1)
        self.assertEqual(self.mails, [self.mail_uno])
        self.assertEqual(recordatorios.enviar(LUNES + timedelta(minutes=15)), 0)
        self.assertEqual(self.mails, [self.mail_uno])

    def test_fuera_de_horario_espera_al_proximo_habil(self):
        sid = self.alta()
        self.le_toca_desde(sid, SABADO - timedelta(hours=49))
        self.assertEqual(recordatorios.enviar(SABADO), 0)
        self.assertEqual(recordatorios.enviar(LUNES.replace(day=16, hour=7, minute=59)), 0)
        self.assertEqual(recordatorios.enviar(LUNES.replace(day=16, hour=8)), 1)

    def test_despues_de_las_18_tampoco_sale(self):
        self.vencida()
        self.assertEqual(recordatorios.enviar(LUNES.replace(hour=18)), 0)
        self.assertEqual(recordatorios.enviar(LUNES.replace(hour=17, minute=59)), 1)

    def test_el_segundo_a_la_semana_y_ahi_se_corta(self):
        sid = self.vencida()
        recordatorios.enviar(LUNES)
        self.assertEqual(recordatorios.enviar(LUNES + timedelta(days=6)), 0)
        self.assertEqual(recordatorios.enviar(LUNES + timedelta(days=7)), 1)
        self.assertEqual(recordatorios.enviar(LUNES + timedelta(days=14)), 0)
        self.assertEqual(len(self.mails), 2)
        self.assertTrue(all(self.columnas(sid, 'recordatorio1_at', 'recordatorio2_at')))

    def test_varias_vencidas_van_en_un_solo_mail(self):
        self.vencida()
        self.vencida(proveedor_nombre='Otro Proveedor SA')
        self.assertEqual(recordatorios.enviar(LUNES), 1)
        self.assertEqual(self.mails, [self.mail_uno])

    def test_no_se_le_recuerda_lo_que_no_esta_pendiente(self):
        autorizada = self.vencida()
        self.firmar(autorizada, self.uno)
        devuelta = self.vencida()
        self.api.post(f'/api/solicitudes/{devuelta}/revisar', json={
            'autorizado_id': self.uno, 'pin': PIN, 'accion': 'observar', 'motivo': 'falta el remito'})
        self.mails.clear()
        self.assertEqual(recordatorios.enviar(LUNES), 0)

    def test_una_vieja_sin_firmante_no_tiene_a_quien_recordarle(self):
        sid = self.vencida()
        self.fijar_avisar_a(sid, '')
        self.assertEqual(recordatorios.enviar(LUNES), 0)

    def test_no_se_le_recuerda_a_quien_ya_no_puede_firmarla(self):
        self.vencida()
        self.fijar_tope(self.uno, 500)
        self.assertEqual(recordatorios.enviar(LUNES), 0)

    def test_las_que_ya_existian_cuentan_desde_que_llegan_los_recordatorios(self):
        # Una base anterior a los recordatorios, con una pendiente de hace 5 días.
        sid = self.alta()
        conn = database.get_db()
        try:
            conn.execute("UPDATE solicitudes SET created_at = datetime('now', 'localtime', '-5 days') "
                         'WHERE id = ?', (sid,))
            for columna in ('aviso_firmante_at', 'recordatorio1_at', 'recordatorio2_at'):
                conn.execute(f'ALTER TABLE solicitudes DROP COLUMN {columna}')
            conn.commit()
        finally:
            conn.close()

        database.init_db()   # el arranque de la versión nueva
        conn = database.get_db()
        try:
            fila = conn.execute('SELECT * FROM solicitudes WHERE id = ?', (sid,)).fetchone()
        finally:
            conn.close()
        ahora = datetime.now()
        self.assertIsNone(recordatorios._que_toca(fila, ahora + timedelta(hours=47)))
        self.assertEqual(recordatorios._que_toca(fila, ahora + timedelta(hours=49)), 'recordatorio1_at')

    def test_cambiar_el_firmante_reinicia_la_cuenta(self):
        sid = self.vencida()
        recordatorios.enviar(LUNES)
        r = self.api.put(f'/api/solicitudes/{sid}', json=self.datos(avisar_a=[self.otro]))
        self.assertEqual(r.status_code, 200, r.get_json())
        aviso, primero, segundo = self.columnas(sid, 'aviso_firmante_at', 'recordatorio1_at',
                                                'recordatorio2_at')
        self.assertIsNotNone(aviso)
        self.assertEqual((primero, segundo), (None, None))


if __name__ == '__main__':
    unittest.main()
