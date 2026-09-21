import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

# Nombre publico de esta app: es el remitente, el asunto y el pie de los mails.
# Se fija aca (y no en el .env solamente) para que no dependa de que la variable
# este cargada: un mail firmado "Neostar" a secas no dice de donde salio.
os.environ.setdefault('APP_NOMBRE', 'Autorizaciones de Compra')
os.environ.setdefault('MAIL_FROM_NOMBRE', os.environ['APP_NOMBRE'])

from models.database import init_db
from routes.autorizados import bp as autorizados_bp
from routes.facturas import bp as facturas_bp
from routes.solicitudes import bp as solicitudes_bp


def crear_app():
    # Los avisos por mail son best-effort: cuando uno no sale, el unico rastro es
    # el log. Sin esto, en Docker no se ve nada por debajo de WARNING.
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
    app.json.ensure_ascii = False
    CORS(app)

    init_db()

    app.register_blueprint(facturas_bp, url_prefix='/api')
    app.register_blueprint(solicitudes_bp, url_prefix='/api')
    app.register_blueprint(autorizados_bp, url_prefix='/api')

    @app.route('/api/health')
    def health():
        return jsonify({'ok': True})

    return app


app = crear_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_ENV') == 'development')
