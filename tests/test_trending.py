import unittest
from unittest.mock import patch, MagicMock
import json
import os
from backend.app import create_app
from backend.database import Database
from backend.models.user import User
from backend.services.tmdb_client import TmdbClient, clear_tmdb_cache


class TestTmdbTrendingClient(unittest.TestCase):
	def setUp(self):
		clear_tmdb_cache()

	def tearDown(self):
		clear_tmdb_cache()

	@patch('requests.get')
	def test_get_trending_movies(self, mock_get):
		mock_resp = MagicMock()
		mock_resp.json.return_value = {
			"page": 1,
			"total_pages": 5,
			"total_results": 100,
			"results": [
				{
					"id": 101,
					"title": "Dune: Part Two",
					"release_date": "2024-03-01",
					"overview": "Paul Atreides unites with Chani...",
					"poster_path": "/czembW0Rk1Ke7ra2Nm69CdpPXVo.jpg",
					"backdrop_path": "/xOMo8BRK7PfcJv9JCnx7s5200SV.jpg",
					"vote_average": 8.3,
					"vote_count": 4500,
					"popularity": 320.5,
					"genre_ids": [878, 12]
				}
			]
		}
		mock_resp.raise_for_status = MagicMock()
		mock_get.return_value = mock_resp

		client = TmdbClient(api_key="mock_key")
		data = client.get_trending(media_type="movie", time_window="day", page=1)

		self.assertIsNotNone(data)
		self.assertEqual(data["page"], 1)
		self.assertEqual(len(data["results"]), 1)
		item = data["results"][0]
		self.assertEqual(item["id"], 101)
		self.assertEqual(item["title"], "Dune: Part Two")
		self.assertEqual(item["year"], 2024)
		self.assertFalse(item["is_tv"])
		self.assertIn("Sci-Fi", item["genres"])
		self.assertIn("Adventure", item["genres"])
		self.assertTrue(item["poster_url"].startswith("https://image.tmdb.org/t/p/w500/"))

		# Verify cache on subsequent call (mock_get should only be called once)
		cached_data = client.get_trending(media_type="movie", time_window="day", page=1)
		self.assertEqual(mock_get.call_count, 1)
		self.assertEqual(cached_data, data)

	@patch('requests.get')
	def test_get_trending_tv(self, mock_get):
		mock_resp = MagicMock()
		mock_resp.json.return_value = {
			"page": 1,
			"total_pages": 1,
			"total_results": 1,
			"results": [
				{
					"id": 202,
					"name": "Shogun",
					"first_air_date": "2024-02-27",
					"overview": "Lord Yoshii Toranaga discovers...",
					"poster_path": "/7O4iVfOMQmdCSxhOg1WnzG1AgYT.jpg",
					"vote_average": 8.7,
					"vote_count": 1200,
					"popularity": 180.2,
					"genre_ids": [18, 10768]
				}
			]
		}
		mock_resp.raise_for_status = MagicMock()
		mock_get.return_value = mock_resp

		client = TmdbClient(api_key="mock_key")
		data = client.get_trending(media_type="tv", time_window="week", page=1)

		self.assertIsNotNone(data)
		item = data["results"][0]
		self.assertEqual(item["title"], "Shogun")
		self.assertEqual(item["year"], 2024)
		self.assertTrue(item["is_tv"])
		self.assertIn("Drama", item["genres"])
		self.assertIn("War & Politics", item["genres"])

	def test_get_trending_no_api_key(self):
		client = TmdbClient(api_key=None)
		data = client.get_trending()
		self.assertIsNone(data)


class TestTrendingAPI(unittest.TestCase):
	def setUp(self):
		self.db_path = "test_trending_ricocx.db"
		if os.path.exists(self.db_path):
			os.remove(self.db_path)
		os.environ["DATABASE_PATH"] = self.db_path

		Database.reset_instance()
		clear_tmdb_cache()

		self.app = create_app()
		self.app.config['TESTING'] = True
		self.client = self.app.test_client()

		self.db = Database()
		self.user = User.create(
			username="trendtester@example.com",
			password="testpassword",
			group_name="User"
		)
		self.token = User.create_session(self.user.id)
		self.client.set_cookie('session_token', self.token)

	def tearDown(self):
		clear_tmdb_cache()
		Database.reset_instance()
		if os.path.exists(self.db_path):
			try:
				os.remove(self.db_path)
			except Exception:
				pass
		if "DATABASE_PATH" in os.environ:
			del os.environ["DATABASE_PATH"]

	def test_trending_unauthenticated(self):
		# No cookie/token
		anon_client = self.app.test_client()
		resp = anon_client.get('/api/trending')
		self.assertEqual(resp.status_code, 401)

	def test_trending_missing_key(self):
		# Ensure settings have no tmdb key
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("tmdb_api_key", ""))
		with patch.dict(os.environ, {"TMDB_API_KEY": ""}):
			resp = self.client.get('/api/trending')
			self.assertEqual(resp.status_code, 503)

	@patch('requests.get')
	def test_trending_endpoint_with_server_match(self, mock_get):
		# Configure TMDb API key in settings
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("tmdb_api_key", "valid_key"))

		# Insert a completed download for "Dune: Part Two"
		self.db.execute(
			"INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
			(self.user.id, "tb_100", "Dune: Part Two", "Dune.Part.Two.2024.mkv", "magnet:?xt=urn:btih:dummy1", "completed", "movie", 4500000000)
		)

		mock_resp = MagicMock()
		mock_resp.json.return_value = {
			"page": 1,
			"total_pages": 2,
			"total_results": 2,
			"results": [
				{
					"id": 101,
					"title": "Dune: Part Two",
					"release_date": "2024-03-01",
					"overview": "Paul Atreides...",
					"poster_path": "/dune.jpg",
					"vote_average": 8.4,
					"vote_count": 3000,
					"popularity": 400.0,
					"genre_ids": [878]
				},
				{
					"id": 102,
					"title": "Civil War",
					"release_date": "2024-04-12",
					"overview": "A journey across a dystopian future America...",
					"poster_path": "/civilwar.jpg",
					"vote_average": 7.1,
					"vote_count": 1500,
					"popularity": 250.0,
					"genre_ids": [28, 18]
				}
			]
		}
		mock_resp.raise_for_status = MagicMock()
		mock_get.return_value = mock_resp

		resp = self.client.get('/api/trending?type=movie&window=day')
		self.assertEqual(resp.status_code, 200)
		data = json.loads(resp.data)

		self.assertEqual(len(data["results"]), 2)

		dune_item = data["results"][0]
		self.assertEqual(dune_item["title"], "Dune: Part Two")
		self.assertTrue(dune_item["in_database"])
		self.assertIsNotNone(dune_item["existing_download"])
		self.assertEqual(dune_item["existing_download"]["status"], "completed")

		civil_war_item = data["results"][1]
		self.assertEqual(civil_war_item["title"], "Civil War")
		self.assertFalse(civil_war_item["in_database"])
		self.assertIsNone(civil_war_item["existing_download"])


if __name__ == '__main__':
	unittest.main()
