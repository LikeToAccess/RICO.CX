from waitress import serve

import app
from settings import (
	HOST,
	PORT
)


def main():
	serve(app.app, host=HOST, port=PORT, threads=12, url_scheme="https")
	# app.app.run(host=HOST, port=PORT, debug=True, ssl_context="adhoc")


if __name__ == "__main__":
	main()
