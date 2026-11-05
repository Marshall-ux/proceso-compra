"""Base de los tests que usan la base de datos y la API.

No es un archivo de tests (no empieza con test_): lo importan los que sí lo son.
Usan una base SQLite temporal (nunca la de data/) y no mandan mails: enviar_mail se
reemplaza por uno que anota destinatarios.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from flask import Flask

from models import database
from routes.solicitudes import bp as solicitudes_bp
from services import avisos
from services.pins import _hash

PIN = '482913'


def sin_env_cajas():
    """Entorno sin ninguna CAJA_*: que los tests usen los defaults del codigo y no
    lo que tenga el .env de la maquina."""
    return {k: v for k, v in os.environ.items() if not k.startswith('CAJA_')}


class ConBase(unittest.TestCase):
    """Base temporal con el roster real de autorizados."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        p = mock.patch.object(database, 'DATABASE_PATH', os.path.join(self.dir, 'app.db'))
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, sin_env_cajas(), clear=True)
        p.start()
        self.addCleanup(p.stop)
        database.init_db()

        # Dos firmantes sin limite y con mail: cualquiera de los dos puede cerrar
        # solo un gasto de cualquier marca.
        conn = database.get_db()
        try:
            filas = conn.execute(
                "SELECT id, email FROM autorizados WHERE activo = 1 AND lista = 'multimarca' "
                "AND monto_autorizado IS NULL AND email LIKE '%@%' ORDER BY id LIMIT 2").fetchall()
            conn.execute('UPDATE autorizados SET pin_hash = ?', (_hash(PIN),))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(len(filas), 2, 'el roster cambio: hacen falta 2 multimarca sin limite con mail')
        (self.uno, self.mail_uno), (self.otro, self.mail_otro) = filas

        self.mails = []
        p = mock.patch.object(avisos, 'enviar_mail',
                              side_effect=lambda to, *a, **k: self.mails.append(to) or True)
        p.start()
        self.addCleanup(p.stop)

    def datos(self, **cambios):
        return {
            'fecha': '05/11/2026', 'empresas': ['HIKARI S.A.'], 'marcas': ['NISSAN'],
            'ubicacion': 'santa_fe', 'proveedor_tipo': 'habitual', 'proveedor_nombre': 'Proveedor SA',
            'cuit': '30-12345678-9', 'tipo_orden': 'cerrada', 'concepto': 'gastos',
            'criticidad': 'urgente', 'solicitado_por': 'Quien Carga', 'monto_total': 1000,
            'moneda': 'ARS', 'avisar_a': [self.uno], 'items': [],
            **cambios,
        }


class ConApi(ConBase):
    def setUp(self):
        super().setUp()
        app = Flask(__name__)
        app.register_blueprint(solicitudes_bp, url_prefix='/api')
        self.api = app.test_client()

    def alta(self, **cambios):
        r = self.api.post('/api/solicitudes', json=self.datos(**cambios))
        self.assertEqual(r.status_code, 201, r.get_json())
        self.mails.clear()
        return r.get_json()['id']

    def firmar(self, sid, quien):
        return self.api.post(f'/api/solicitudes/{sid}/autorizar',
                             json={'autorizado_id': quien, 'pin': PIN})

    def fijar_avisar_a(self, sid, valor):
        conn = database.get_db()
        try:
            conn.execute('UPDATE solicitudes SET avisar_a = ? WHERE id = ?', (valor, sid))
            conn.commit()
        finally:
            conn.close()

    def fijar_tope(self, autorizado_id, tope):
        """Como si le hubieran bajado el tope después de cargar la solicitud."""
        conn = database.get_db()
        try:
            conn.execute('UPDATE autorizados SET monto_autorizado = ? WHERE id = ?',
                         (tope, autorizado_id))
            conn.commit()
        finally:
            conn.close()
