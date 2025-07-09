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
            ssl_context="adhoc",
            use_reloader=USE_RELOADER
        )
    else:
        serve(
            app.app,
            host=HOST,
            port=PORT,
            threads=12,
            url_scheme="https"
        )
    # app.app.run(host=HOST, port=PORT, ssl_context="adhoc")


if __name__ == "__main__":
    main()
