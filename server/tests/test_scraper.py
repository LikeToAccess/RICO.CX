import unittest
from scraper import Goojara as Scraper  # type: ignore[import-untyped]


class CustomTestCase(unittest.TestCase):

	def assertStartsWith(self, actual, prefix, msg=None):
		"""Asserts that the actual string starts with the specified prefix.
		
		Args:
			actual (str): The actual string.
			prefix (str): The expected prefix.
			msg (str, optional): The assertion error message.

		Raises:
			AssertionError: If the actual string does not start with the specified prefix.
		"""
		self.assertTrue(actual.startswith(prefix), msg)


class TestRequests(unittest.TestCase):

	def setUp(self):
		self.scraper = Scraper(init=False)

	def test_search_one(self):
		query = "saw x"
		for _ in range(1):
			result = self.scraper.search_one(query)[0]
			print(result, "(search_one)")
			self.assertTrue(result["page_url"])
			self.assertEqual(result["title"], "Saw X")
			self.assertEqual(result["year"], "2023")

	def test_get_video_data(self):
		query = "saw x"
		result = self.scraper.search_one(query)[0]
		page_url = result["page_url"]
		for _ in range(1):
			video_data = self.scraper.get_video_data(page_url)
			print(video_data, "(video_data)")
			self.assertTrue(result["page_url"])
			self.assertEqual(video_data["title"], "Saw X (2023) {tmdb-951491}/Saw X (2023) {tmdb-951491}")
			self.assertEqual(video_data["year"], "2023")
			self.assertEqual(video_data["catagory"], "movie")

	def test_get_video_data_tv_show(self):
		page_url = "https://www.goojara.to/eDJG9X"
		for _ in range(1):
			video_data = self.scraper.get_video_data(page_url)
			print(video_data, "(video_data)")
			self.assertTrue(video_data)
			self.assertEqual(video_data["title"], "Rick and Morty (2013) {tmdb-60625}/Rick and Morty (2013) - S07E04 - That's Amorte")
			self.assertEqual(video_data["year"], "2013")
			self.assertEqual(video_data["catagory"], "episode")


class TestScraper(CustomTestCase, unittest.TestCase):

	def setUp(self):
		self.scraper = Scraper()

	def tearDown(self):
		self.scraper.close()

	def test_get_video_url(self):
		query = "saw x"
		result = self.scraper.search_one(query)[0]
		page_url = result["page_url"]
		for _ in range(1):
			video_url = self.scraper.get_video_url(page_url)
			print(video_url, "(video_url)")
			self.assertTrue(video_url)
			self.assertStartsWith(video_url, "https://")


if __name__ == "__main__":
	unittest.main()
