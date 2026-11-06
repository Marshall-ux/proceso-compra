"""El chequeo de salud que consulta Docker (healthcheck en docker-compose.yml).

Contesta 200 si la base se puede leer y 503 si no: es lo que decide si `docker ps`
muestra el backend como healthy o unhealthy.
"""

import importlib
import logging
import os
from unittest import mock

from models import database
from tests.apoyo import ConBase


class TestHealth(ConBase):
    def setUp(self):
        super().setUp()
        # app.py arma la app al importarse. Sin el hilo de recordatorios, sin pisar la
        # configuración de logging de los demás tests y sin los avisos de clave de ejemplo.
        logging.disable(logging.WARNING)
        try:
            with mock.patch.dict(os.environ, {'RECORDATORIOS': '0'}), \
                    mock.patch.object(logging, 'basicConfig'):
                modulo = importlib.import_module('app')
        finally:
            logging.disable(logging.NOTSET)
        self.api = modulo.app.test_client()

    def test_con_la_base_contesta_ok(self):
        r = self.api.get('/api/health')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {'ok': True})

    def test_sin_la_base_contesta_503(self):
        # Como con el volumen sin montar: el archivo está vacío, sin tablas.
        with mock.patch.object(database, 'DATABASE_PATH', os.path.join(self.dir, 'vacia.db')), \
                self.assertLogs('app', 'ERROR'):
            r = self.api.get('/api/health')
        self.assertEqual(r.status_code, 503)
        self.assertFalse(r.get_json()['ok'])
