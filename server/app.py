import os

from flask import Flask, jsonify
from flask_cors import CORS

from models.database import init_db
from routes.autorizados import bp as autorizados_bp
from routes.facturas import bp as facturas_bp
from routes.solicitudes import bp as solicitudes_bp


def crear_app():
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
