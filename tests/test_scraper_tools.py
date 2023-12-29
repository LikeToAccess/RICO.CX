import unittest
from scraper_tools import ScraperTools, TMDbTools


class TestScraper(unittest.TestCase):

	def setUp(self):
		self.scraper = ScraperTools()

	def tearDown(self):
		self.scraper.close()

	def test_open_link(self):
		self.scraper.open_link("https://www.google.com/")
		current_url = self.scraper.current_url()
		self.assertEqual(current_url, "https://www.google.com/")

	def test_redirect(self):
		self.scraper.redirect("https://www.google.com/")
		current_url = self.scraper.current_url()
		self.assertEqual(current_url, "https://www.google.com/")

class TestTMDb(unittest.TestCase):

	def setUp(self):
		self.tmdb = TMDbTools()

	def test_search_movies(self):
		results = self.tmdb.search_movies("saw x")
		print(results)
		self.assertTrue(results)

	def test_search_tv_show(self):
		result = self.tmdb.search_tv_show("rick and morty")
		print(result)
		self.assertTrue(result)
		self.assertEqual(result["first_air_date"][:4], "2013")


if __name__ == "__main__":
	unittest.main()
