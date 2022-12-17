from waitress import serve

import app
from settings import (
	HOST,
	PORT
)


def main():
	serve(app.app, host=HOST, port=PORT, threads=12)
	# app.app.run(host="0.0.0.0", port=8080, debug=True)


if __name__ == "__main__":
	main()
