from waitress import serve

import app
from settings import (
    HOST,
    PORT,
    USE_RELOADER,
    DEBUG_MODE
)


def main():
    if DEBUG_MODE:
        app.app.run(
            host=HOST,
            port=PORT,
            debug=DEBUG_MODE,
            use_reloader=USE_RELOADER
        )
    else:
            app.app.run(host="0.0.0.0", port=9000, ssl_context='adhoc')

# serve(app, host="0.0.0.0", port=9000)
    # app.app.run(host=HOST, port=PORT, ssl_context="adhoc")


if __name__ == "__main__":
    main()
