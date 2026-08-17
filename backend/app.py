import logging
import os
from typing import Any, Optional
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS  # type: ignore[import-untyped]
from flask_socketio import SocketIO  # type: ignore[import-untyped]
from werkzeug.middleware.proxy_fix import ProxyFix
from .database import Database

logger = logging.getLogger(__name__)

socketio_async_mode = os.environ.get("SOCKETIO_ASYNC_MODE")
socketio = SocketIO(cors_allowed_origins="*", async_mode=socketio_async_mode)


def create_app() -> Flask:
	"""
	Factory function to create and configure the Flask application.
	"""
	current_dir = os.path.dirname(os.path.abspath(__file__))
	dist_dir = os.path.abspath(os.path.join(current_dir, '../frontend/dist'))

	if os.path.exists(dist_dir):
		static_dir = dist_dir
		logger.info("Flask: Serving static assets from Vite build folder: %s", static_dir)
	else:
		static_dir = os.path.abspath(os.path.join(current_dir, '../frontend'))
		logger.info("Flask: Serving static assets from source folder: %s", static_dir)

	app = Flask(__name__, static_folder=static_dir, static_url_path='/')

	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

	app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)  # type: ignore[method-assign]

	CORS(app, supports_credentials=True)

	app.secret_key = os.environ.get("FLASK_SECRET_KEY", "rico_cx_secret_key_129837")

	Database()

	from .routes.api import api_bp  # pylint: disable=import-outside-toplevel
	app.register_blueprint(api_bp, url_prefix='/api')

	socketio.init_app(app)

	from .routes.api import init_download_resumption  # pylint: disable=import-outside-toplevel
	init_download_resumption()

	@app.before_request
	def block_sensitive_files() -> Optional[Any]:
		req_path = request.path.lower()
		filename = os.path.basename(req_path)
		sensitive_exts = ['.env', '.db', '.sqlite', '.py', '.sql', '.sh', '.bak', '.log', '.err', '.md', '.yml', '.yaml']
		if filename.startswith('.') or any(req_path.endswith(ext) for ext in sensitive_exts):
			return jsonify({"error": "Access denied"}), 403
		return None

	@app.route('/')
	def serve() -> Any:
		if app.static_folder:
			return send_from_directory(app.static_folder, 'index.html')
		return jsonify({"error": "Static folder not set"}), 500

	@app.route('/<path:path>')
	def catch_all(path: str) -> Any:
		if not app.static_folder:
			return jsonify({"error": "Static folder not set"}), 500

		filename = os.path.basename(path)
		sensitive_exts = ['.env', '.db', '.sqlite', '.py', '.sql', '.sh', '.bak', '.log', '.err', '.md', '.yml', '.yaml']
		if filename.startswith('.') or any(path.lower().endswith(ext) for ext in sensitive_exts):
			return jsonify({"error": "Access denied"}), 403

		safe_path = os.path.abspath(os.path.join(app.static_folder, path))
		if not safe_path.startswith(os.path.abspath(app.static_folder)):
			return jsonify({"error": "Access denied"}), 403

		if path != "" and os.path.exists(safe_path) and os.path.isfile(safe_path):
			return send_from_directory(app.static_folder, path)

		return send_from_directory(app.static_folder, 'index.html')

	@app.errorhandler(404)
	def page_not_found(_e: Any) -> Any:
		if request.path.startswith('/api/'):
			return jsonify({"error": "API route not found"}), 404
		if app.static_folder:
			return send_from_directory(app.static_folder, 'index.html'), 200
		return jsonify({"error": "Static folder not set"}), 500

	return app