from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix
from .database import Database
import os
import logging

logger = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

def create_app():
    # Determine the static folder. If frontend/dist exists, serve from it. Otherwise, serve from frontend/ directly.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.abspath(os.path.join(current_dir, '../frontend/dist'))
    
    if os.path.exists(dist_dir):
        static_dir = dist_dir
        logger.info(f"Flask: Serving static assets from Vite build folder: {static_dir}")
    else:
        static_dir = os.path.abspath(os.path.join(current_dir, '../frontend'))
        logger.info(f"Flask: Serving static assets from source folder: {static_dir}")
        
    app = Flask(__name__, static_folder=static_dir, static_url_path='/')
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Configure reverse proxy headers support
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    
    # Setup CORS
    CORS(app, supports_credentials=True)
    
    # Set a secret key for flask sessions (optional but good practice)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "rico_cx_secret_key_129837")
    
    # Initialize DB (creates files and tables)
    Database() 

    # Register Blueprints
    from .routes.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Initialize socketio with the app
    socketio.init_app(app)

    @app.route('/')
    def serve():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/<path:path>')
    def catch_all(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')

    @app.errorhandler(404)
    def page_not_found(e):
        from flask import request, jsonify
        if request.path.startswith('/api/'):
            return jsonify({"error": "API route not found"}), 404
        return send_from_directory(app.static_folder, 'index.html'), 200

    return app