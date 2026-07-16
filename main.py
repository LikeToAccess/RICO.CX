import os
import sys
from backend.app import create_app, socketio
from dotenv import load_dotenv

load_dotenv()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG_MODE", "True").lower() == "true"
    use_ssl = os.environ.get("USE_SSL", "True").lower() == "true"
    
    ssl_context = 'adhoc' if use_ssl else None
    
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, ssl_context=ssl_context, allow_unsafe_werkzeug=True)
