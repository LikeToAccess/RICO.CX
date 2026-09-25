import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from backend.models.result import TorrentResult, AggregatedResult
from backend.services.tmdb_client import TmdbClient, clear_tmdb_cache
from backend.routes.api import find_tv_show_dir, scan_season_episodes_on_disk
from backend.app import create_app
from backend.database import Database
from backend.models.user import User


class TestTvTracker(unittest.TestCase):
	def setUp(self):
		clear_tmdb_cache()

	def test_season_pack_vs_single_episode_detection(self):
		# Season pack: has season but no episode
		sp1 = TorrentResult(
			title="Severance.S01.1080p.ATVP.WEB-DL.DDP5.1.Atmos.H.264-FLUX",
			size=15 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:sp1",
			seeders=50,
			leechers=5,
			indexer="1337x"
		)
		self.assertTrue(sp1.is_tv)
		self.assertEqual(sp1.season, 1)
		self.assertIsNone(sp1.episode)
		self.assertTrue(sp1.is_season_pack)
		self.assertTrue(sp1.to_dict()["is_season_pack"])

		# Season pack: explicit "Season 2 Complete"
		sp2 = TorrentResult(
			title="Breaking Bad Season 2 Complete 720p HDTV x264",
			size=8 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:sp2",
			seeders=30,
			leechers=2,
			indexer="1337x"
		)
		self.assertTrue(sp2.is_tv)
		self.assertEqual(sp2.season, 2)
		self.assertIsNone(sp2.episode)
		self.assertTrue(sp2.is_season_pack)

		# Single episode: has both season and episode
		ep1 = TorrentResult(
			title="Severance.S01E04.The.You.You.Are.1080p.WEB-DL",
			size=1 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:ep1",
			seeders=100,
			leechers=10,
			indexer="1337x"
		)
		self.assertTrue(ep1.is_tv)
		self.assertEqual(ep1.season, 1)
		self.assertEqual(ep1.episode, 4)
		self.assertFalse(ep1.is_season_pack)
		self.assertFalse(ep1.to_dict()["is_season_pack"])

		# Multi-episode pack: S01E01-E04
		multi = TorrentResult(
			title="Severance.S01E01-E04.1080p.WEB-DL",
			size=4 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:multi",
			seeders=20,
			leechers=1,
			indexer="1337x"
		)
		self.assertTrue(multi.is_tv)
		self.assertTrue(multi.is_season_pack)

		# Movie: neither tv nor season pack
		movie = TorrentResult(
			title="Inception.2010.1080p.BluRay.x264",
			size=2 * 1024 * 1024 * 1024,
			download_url="magnet:?xt=urn:btih:movie",
			seeders=500,
			leechers=20,
			indexer="1337x"
		)
		self.assertFalse(movie.is_tv)
		self.assertFalse(movie.is_season_pack)

	def test_aggregated_result_tmdb_id(self):
		agg = AggregatedResult("Severance", 2022, True)
		self.assertIsNone(agg.tmdb_id)
		agg.tmdb_id = 95396
		d = agg.to_dict()
		self.assertEqual(d["tmdb_id"], 95396)

	@patch('requests.get')
	def test_tmdb_get_tv_details(self, mock_get):
		mock_resp = MagicMock()
		mock_resp.json.return_value = {
			"id": 95396,
			"name": "Severance",
			"first_air_date": "2022-02-18",
			"number_of_seasons": 2,
			"number_of_episodes": 19,
			"overview": "Mark leads a team of office workers...",
			"poster_path": "/poster.jpg",
			"backdrop_path": "/backdrop.jpg",
			"status": "Returning Series",
			"genres": [{"id": 18, "name": "Drama"}, {"id": 878, "name": "Sci-Fi"}],
			"seasons": [
				{
					"season_number": 0,
					"name": "Specials",
					"episode_count": 2
				},
				{
					"season_number": 1,
					"name": "Season 1",
					"episode_count": 9,
					"air_date": "2022-02-18",
					"poster_path": "/s1.jpg",
					"overview": "Season 1 overview"
				},
				{
					"season_number": 2,
					"name": "Season 2",
					"episode_count": 10,
					"air_date": "2025-01-17",
					"poster_path": "/s2.jpg",
					"overview": "Season 2 overview"
				}
			]
		}
		mock_resp.raise_for_status = MagicMock()
		mock_get.return_value = mock_resp

		client = TmdbClient(api_key="test_key")
		details = client.get_tv_details(95396)

		self.assertIsNotNone(details)
		self.assertEqual(details["id"], 95396)
		self.assertEqual(details["name"], "Severance")
		self.assertEqual(details["year"], 2022)
		# Season 0 (specials) excluded from main seasons list
		self.assertEqual(len(details["seasons"]), 2)
		self.assertEqual(details["seasons"][0]["season_number"], 1)
		self.assertEqual(details["seasons"][0]["episode_count"], 9)
		self.assertEqual(details["seasons"][1]["season_number"], 2)
		self.assertEqual(details["seasons"][1]["episode_count"], 10)

	@patch('requests.get')
	def test_tmdb_get_season_details(self, mock_get):
		mock_resp = MagicMock()
		mock_resp.json.return_value = {
			"id": 12345,
			"season_number": 1,
			"name": "Season 1",
			"air_date": "2022-02-18",
			"overview": "Season overview",
			"poster_path": "/s1.jpg",
			"episodes": [
				{
					"episode_number": 1,
					"name": "Good News About Hell",
					"air_date": "2022-02-18",
					"overview": "Episode 1 summary",
					"vote_average": 8.3,
					"still_path": "/still1.jpg"
				},
				{
					"episode_number": 2,
					"name": "Half Loop",
					"air_date": "2022-02-18",
					"overview": "Episode 2 summary",
					"vote_average": 8.1,
					"still_path": "/still2.jpg"
				}
			]
		}
		mock_resp.raise_for_status = MagicMock()
		mock_get.return_value = mock_resp

		client = TmdbClient(api_key="test_key")
		season = client.get_season_details(95396, 1)

		self.assertIsNotNone(season)
		self.assertEqual(season["season_number"], 1)
		self.assertEqual(len(season["episodes"]), 2)
		self.assertEqual(season["episodes"][0]["name"], "Good News About Hell")
		self.assertEqual(season["episodes"][0]["episode_number"], 1)

	def test_find_tv_show_dir_and_scan_episodes(self):
		temp_root = tempfile.mkdtemp()
		try:
			tv_shows_dir = os.path.join(temp_root, "TV SHOWS")
			os.makedirs(tv_shows_dir)

			# Create show directory with TMDb ID tag
			show_folder = os.path.join(tv_shows_dir, "Severance (2022) {tmdb-95396}")
			s1_folder = os.path.join(show_folder, "Season 01")
			os.makedirs(s1_folder)

			# Create dummy episode files
			f1 = os.path.join(s1_folder, "Severance - S01E01 - Good News About Hell.mkv")
			f2 = os.path.join(s1_folder, "Severance - S01E02 - Half Loop.mkv")
			with open(f1, "w") as f:
				f.write("dummy content e01")
			with open(f2, "w") as f:
				f.write("dummy content e02")

			# Test find_tv_show_dir by TMDb ID
			found_by_id = find_tv_show_dir(temp_root, 95396, "Severance", 2022)
			self.assertEqual(found_by_id, show_folder)

			# Test find_tv_show_dir by title when ID not provided
			found_by_title = find_tv_show_dir(temp_root, None, "Severance", 2022)
			self.assertEqual(found_by_title, show_folder)

			# Test scanning episodes on disk
			disk_eps = scan_season_episodes_on_disk(show_folder, 1)
			self.assertIn(1, disk_eps)
			self.assertIn(2, disk_eps)
			self.assertNotIn(3, disk_eps)
			self.assertEqual(disk_eps[1]["filename"], "Severance - S01E01 - Good News About Hell.mkv")
			self.assertGreater(disk_eps[1]["size"], 0)

			# Test scanning season 2 (empty/absent)
			disk_eps_s2 = scan_season_episodes_on_disk(show_folder, 2)
			self.assertEqual(len(disk_eps_s2), 0)
		finally:
			shutil.rmtree(temp_root, ignore_errors=True)


class TestTvApiRoutes(unittest.TestCase):
	def setUp(self):
		self.temp_dir = tempfile.mkdtemp()
		self.db_path = os.path.join(self.temp_dir, "test.db")
		os.environ["DATABASE_PATH"] = self.db_path
		os.environ["ROOT_LIBRARY_LOCATION"] = self.temp_dir
		os.environ["TMDB_API_KEY"] = "test_tmdb_key"
		Database.reset_instance()

		self.app = create_app()
		self.app.config["TESTING"] = True
		self.client = self.app.test_client()

		self.db = Database()
		self.user = User.create(
			username="tv_tester@example.com",
			password="testpassword",
			group_name="Admin"
		)
		self.token = User.create_session(self.user.id)
		self.client.set_cookie('session_token', self.token)

	def tearDown(self):
		Database.reset_instance()
		if "DATABASE_PATH" in os.environ:
			del os.environ["DATABASE_PATH"]
		if "ROOT_LIBRARY_LOCATION" in os.environ:
			del os.environ["ROOT_LIBRARY_LOCATION"]
		if "TMDB_API_KEY" in os.environ:
			del os.environ["TMDB_API_KEY"]
		shutil.rmtree(self.temp_dir, ignore_errors=True)

	@patch.object(TmdbClient, 'get_tv_details')
	def test_api_tv_details_route(self, mock_get_tv_details):
		mock_get_tv_details.return_value = {
			"id": 95396,
			"name": "Severance",
			"year": 2022,
			"first_air_date": "2022-02-18",
			"overview": "Mark leads a team...",
			"poster_url": "https://image.tmdb.org/t/p/w300/poster.jpg",
			"backdrop_url": None,
			"number_of_seasons": 1,
			"number_of_episodes": 9,
			"genres": ["Drama", "Sci-Fi"],
			"seasons": [
				{
					"season_number": 1,
					"name": "Season 1",
					"episode_count": 9,
					"air_date": "2022-02-18",
					"poster_url": None,
					"overview": ""
				}
			]
		}

		# Create local episode file for season 1
		tv_dir = os.path.join(self.temp_dir, "TV SHOWS", "Severance (2022) {tmdb-95396}", "Season 01")
		os.makedirs(tv_dir)
		for ep_i in range(1, 10):  # 9 episodes -> complete!
			with open(os.path.join(tv_dir, f"Severance - S01E{ep_i:02d}.mkv"), "w") as f:
				f.write("content")

		resp = self.client.get(
			"/api/tv/details?tv_id=95396&title=Severance",
			headers={"Authorization": f"Bearer {self.token}"}
		)
		self.assertEqual(resp.status_code, 200)
		data = resp.get_json()

		self.assertEqual(data["tv_id"], 95396)
		self.assertEqual(data["title"], "Severance")
		self.assertTrue(data["on_server"])
		s1 = data["seasons"][0]
		self.assertEqual(s1["season_number"], 1)
		self.assertEqual(s1["episodes_on_disk"], 9)
		self.assertEqual(s1["missing_count"], 0)
		self.assertEqual(s1["status"], "complete")

	@patch.object(TmdbClient, 'get_season_details')
	def test_api_tv_season_route(self, mock_get_season_details):
		mock_get_season_details.return_value = {
			"id": 12345,
			"season_number": 1,
			"name": "Season 1",
			"air_date": "2022-02-18",
			"overview": "Season 1 overview",
			"poster_url": None,
			"episodes": [
				{
					"episode_number": 1,
					"name": "Good News About Hell",
					"air_date": "2022-02-18",
					"overview": "Ep 1",
					"vote_average": 8.5,
					"still_url": None
				},
				{
					"episode_number": 2,
					"name": "Half Loop",
					"air_date": "2022-02-25",
					"overview": "Ep 2",
					"vote_average": 8.3,
					"still_url": None
				},
				{
					"episode_number": 3,
					"name": "In Perpetuity",
					"air_date": "2022-03-04",
					"overview": "Ep 3",
					"vote_average": 8.4,
					"still_url": None
				}
			]
		}

		# Put only episode 1 and 2 on disk (episode 3 is missing)
		tv_dir = os.path.join(self.temp_dir, "TV SHOWS", "Severance (2022) {tmdb-95396}", "Season 01")
		os.makedirs(tv_dir)
		with open(os.path.join(tv_dir, "Severance - S01E01.mkv"), "w") as f:
			f.write("content 1")
		with open(os.path.join(tv_dir, "Severance - S01E02.mkv"), "w") as f:
			f.write("content 2")

		resp = self.client.get(
			"/api/tv/season?tv_id=95396&season=1&title=Severance",
			headers={"Authorization": f"Bearer {self.token}"}
		)
		self.assertEqual(resp.status_code, 200)
		data = resp.get_json()

		self.assertEqual(data["season_number"], 1)
		self.assertEqual(data["total_episodes"], 3)
		self.assertEqual(data["on_server_count"], 2)
		self.assertEqual(data["missing_count"], 1)
		self.assertFalse(data["is_complete"])

		eps = data["episodes"]
		self.assertTrue(eps[0]["on_server"])
		self.assertTrue(eps[1]["on_server"])
		self.assertFalse(eps[2]["on_server"])


if __name__ == '__main__':
	unittest.main()
