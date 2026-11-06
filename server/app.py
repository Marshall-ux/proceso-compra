import logging
import os
import sqlite3

from flask import Flask, jsonify
from flask_cors import CORS

# Nombre publico de esta app: es el remitente, el asunto y el pie de los mails.
# Se fija aca (y no en el .env solamente) para que no dependa de que la variable
# este cargada: un mail firmado "Neostar" a secas no dice de donde salio.
os.environ.setdefault('APP_NOMBRE', 'Autorizaciones de Compra')
os.environ.setdefault('MAIL_FROM_NOMBRE', os.environ['APP_NOMBRE'])

from models.database import get_db, init_db
from services import admin, autopack, recordatorios
from routes.autorizados import bp as autorizados_bp
from routes.facturas import bp as facturas_bp
from routes.solicitudes import bp as solicitudes_bp


def crear_app():
    # Los avisos por mail son best-effort: cuando uno no sale, el unico rastro es
    # el log. Sin esto, en Docker no se ve nada por debajo de WARNING.
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    # Una clave de ejemplo en producción no protege nada: que quede a la vista en el log.
    log = logging.getLogger(__name__)
    if admin.usando_default():
        log.warning('ADMIN_PASSWORD es una clave de ejemplo: configurá una propia en el .env')
    if autopack.usando_default():
        log.warning('AUTOPACK_PASSWORD es la clave por defecto: configurá una propia en el .env')

    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
    app.json.ensure_ascii = False
    CORS(app)

    init_db()

    # Recordatorios al firmante (48 h y una semana después, en días hábiles). Se apagan
    # con RECORDATORIOS=0, por ejemplo para una copia de prueba con mail de verdad.
    if os.environ.get('RECORDATORIOS', '1') != '0':
        recordatorios.iniciar()

    app.register_blueprint(facturas_bp, url_prefix='/api')
    app.register_blueprint(solicitudes_bp, url_prefix='/api')
    app.register_blueprint(autorizados_bp, url_prefix='/api')

    # Lo consulta el healthcheck de Docker (docker-compose.yml) para el estado que muestra
    # `docker ps`. Además de que el proceso conteste, lee la base: con el volumen sin
    # montar o la base rota, la app arranca igual pero no sirve, y tiene que verse.
    @app.route('/api/health')
    def health():
        try:
            conn = get_db()
            try:
                conn.execute('SELECT 1 FROM solicitudes LIMIT 1').fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            log.exception('health: la base no responde')
            return jsonify({'ok': False, 'error': 'la base no responde'}), 503
        return jsonify({'ok': True})

    return app


app = crear_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_ENV') == 'development')
