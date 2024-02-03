# -*- coding: utf-8 -*-
# filename          : test_app.py
# description       : Unit Tests for the app.py file
# author            : Ian Ault
# email             : rico@rico.cx
# date              : 12-28-2023
# version           : v1.0
# usage             : python -m unittest tests/test_app.py
# notes             :
# license           : MIT
# py version        : 3.12.0
#==============================================================================
import os
import unittest

import app
# import waitress_serve
from settings import (
	ROOT_LIBRARY_LOCATION
)


class TestDownload(unittest.TestCase):

	def setUp(self):
		# app.app.run(host=HOST, port=PORT, debug=DEBUG_MODE, ssl_context="adhoc", use_reloader=USE_RELOADER)
		self.path = os.path.join(
			ROOT_LIBRARY_LOCATION,
			"MOVIES",
			"Saw X (2023) {tmdb-951491}",
			"Saw X (2023) {tmdb-951491}.mp4")
		if os.path.exists(self.path):
			os.remove(self.path)
		# waitress_serve.main()

	def tearDown(self):
		self.setUp()

	@unittest.skip("Skipping test_download")
	def test_download(self):
		query = "saw x"
		result = app.searchone_api(query)[0]["data"][0]
		print(result, "(search_one -> result)")
		page_url = result["page_url"]
		download_result = app.download_api(page_url)
		print(download_result, "(download_result)")
		self.assertTrue(download_result[0]["message"] == "OK")
		self.assertTrue(os.path.exists(self.path))


if __name__ == "__main__":
	unittest.main()
