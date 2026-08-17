import unittest
from unittest.mock import patch, MagicMock
import json
import os
from backend.app import create_app
from backend.database import Database
from backend.models.user import User

class TestAPI(unittest.TestCase):
	def setUp(self):
		# Configure DATABASE_PATH to isolate database tests
		self.db_path = "test_api_ricocx.db"
		if os.path.exists(self.db_path):
			os.remove(self.db_path)
		os.environ["DATABASE_PATH"] = self.db_path
		
		# Reset Database class singleton instance
		Database.reset_instance()
		
		self.app = create_app()
		self.app.config['TESTING'] = True
		self.client = self.app.test_client()
		
		# Create test user and session for authentication
		self.db = Database()
		self.user = User.create(
			username="test@example.com",
			password="testpassword",
			group_name="User"
		)
		self.token = User.create_session(self.user.id)
		self.client.set_cookie('session_token', self.token)

	def tearDown(self):
		# Reset singleton instance
		Database.reset_instance()
		if os.path.exists(self.db_path):
			try:
				os.remove(self.db_path)
			except Exception:
				pass
		if "DATABASE_PATH" in os.environ:
			del os.environ["DATABASE_PATH"]

	@patch('requests.get')
	def test_search_generic(self, mock_get):
		# Mock Prowlarr search API response
		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.json.return_value = [
			{
				"title": "Inception 2010 1080p BluRay x264",
				"guid": "http://example.com/inception",
				"size": 2147483648,
				"indexer": "PublicIndexer",
				"downloadUrl": "magnet:?xt=urn:btih:ed0c184478144062828b211f6d3f3f504386b72d",
				"infoUrl": "http://example.com/info",
				"seeders": 100,
				"peers": 10
			}
		]
		mock_get.return_value = mock_resp

		# Configure server settings with api key so SearchClient tries to search
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("prowlarr_api_key", "dummy_prowlarr_key"))

		response = self.client.get('/api/search?q=Inception')
		data = json.loads(response.data)
		
		self.assertEqual(response.status_code, 200)
		self.assertEqual(data['type'], 'search_results')
		self.assertTrue(len(data['data']) > 0)
		self.assertEqual(data['data'][0]['clean_title'], 'Inception')

	def test_search_magnet(self):
		magnet = "magnet:?xt=urn:btih:ed0c184478144062828b211f6d3f3f504386b72d&dn=Avatar+2009"
		import urllib.parse
		response = self.client.get(f'/api/search?q={urllib.parse.quote(magnet)}')
		data = json.loads(response.data)
		
		self.assertEqual(response.status_code, 200)
		self.assertEqual(data['type'], 'search_results')
		self.assertTrue(len(data['data']) > 0)
		self.assertEqual(data['data'][0]['clean_title'], 'Avatar')
		self.assertEqual(data['data'][0]['year'], 2009)
		self.assertEqual(data['data'][0]['downloads'][0]['download_url'], magnet)

	@patch('requests.get')
	def test_search_magnet_with_torbox_metadata(self, mock_get):
		# Configure server settings with torbox API key so it tries to query Torbox
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("torbox_api_key", "dummy_torbox_key"))

		# Mock Torbox metadata response from checkcached
		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.json.return_value = {
			"success": True,
			"data": {
				"ed0c184478144062828b211f6d3f3f504386b72d": {
					"name": "Avatar 2009 Special Edition",
					"size": 4831838208, # 4.5 GB
					"hash": "ed0c184478144062828b211f6d3f3f504386b72d"
				}
			}
		}
		mock_get.return_value = mock_resp

		magnet = "magnet:?xt=urn:btih:ed0c184478144062828b211f6d3f3f504386b72d&dn=Avatar+2009"
		import urllib.parse
		response = self.client.get(f'/api/search?q={urllib.parse.quote(magnet)}')
		data = json.loads(response.data)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(data['type'], 'search_results')
		self.assertEqual(data['data'][0]['clean_title'], 'Avatar')
		self.assertEqual(data['data'][0]['downloads'][0]['title'], 'Avatar 2009 Special Edition')
		self.assertEqual(data['data'][0]['size_range'], '4.5 GB')

	@patch('requests.get')
	def test_search_magnet_with_torbox_hash_name_fallback(self, mock_get):
		# When Torbox checkcached returns the raw hash as the name, the dn= title must be preserved
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("torbox_api_key", "dummy_torbox_key"))

		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.json.return_value = {
			"success": True,
			"data": {
				"fddd40b43bf276f03ba25fe12a35510486945aae": {
					"name": "fddd40b43bf276f03ba25fe12a35510486945aae",
					"size": 13544724221,
					"hash": "fddd40b43bf276f03ba25fe12a35510486945aae"
				}
			}
		}
		mock_get.return_value = mock_resp

		magnet = "magnet:?xt=urn:btih:FDDD40B43BF276F03BA25FE12A35510486945AAE&dn=Pantheon+%3A+Season+01+S01+%5B2022%5D+1080p+AMZN+WebRip+x265+DDP+5.1+Kira+%5BSEV%5D&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337"
		import urllib.parse
		response = self.client.get(f'/api/search?q={urllib.parse.quote(magnet)}')
		data = json.loads(response.data)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(data['type'], 'search_results')
		self.assertEqual(len(data['data']), 1)
		card = data['data'][0]
		self.assertEqual(card['clean_title'], "Pantheon")
		self.assertEqual(card['year'], 2022)
		self.assertTrue(card['is_tv'])
		self.assertEqual(card['downloads'][0]['season'], 1)
		self.assertEqual(card['downloads'][0]['size'], 13544724221)

	def test_user_settings(self):
		# Change user to Admin to allow settings access
		self.user.group_id = 1
		self.user.save()

		# Test getting default settings (should return fallback default values)
		response = self.client.get('/api/settings')
		data = json.loads(response.data)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(data, {
			"prowlarr_url": "",
			"prowlarr_api_key": "",
			"torbox_api_key": "",
			"library_path": "./library",
			"tmdb_api_key": ""
		})

		# Test updating settings
		new_settings = {
			"prowlarr_url": "http://localhost:9696",
			"prowlarr_api_key": "new_prowlarr_key",
			"torbox_api_key": "new_torbox_key",
			"library_path": "/media/library"
		}
		response = self.client.post(
			'/api/settings', 
			data=json.dumps(new_settings),
			content_type='application/json'
		)
		self.assertEqual(response.status_code, 200)
		res_data = json.loads(response.data)
		self.assertEqual(res_data["status"], "updated")
		self.assertEqual(res_data["settings"]["torbox_api_key"], "new_torbox_key")
		
		# Verify update persists via GET
		response = self.client.get('/api/settings')
		data = json.loads(response.data)
		self.assertEqual(data['prowlarr_api_key'], 'new_prowlarr_key')
		self.assertEqual(data['library_path'], '/media/library')

	@patch('backend.routes.api.TorboxClient')
	@patch('backend.routes.api.TmdbClient')
	@patch('backend.services.tmdb_client.TmdbClient')
	@patch('backend.routes.api.socketio')
	@patch('requests.get')
	@patch('time.sleep')
	def test_tv_show_downloads_tmdb_tag_formatting_and_cleanup(self, mock_sleep, mock_get, mock_socketio, mock_tmdb_services_class, mock_tmdb_routes_class, mock_torbox_routes_class):
		# 1. Setup server settings
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("torbox_api_key", "dummy_torbox_key"))
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("tmdb_api_key", "dummy_tmdb_key"))
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("library_path", "./test_library"))

		# 2. Setup TMDB mocks
		mock_tmdb1 = mock_tmdb_routes_class.return_value
		mock_tmdb1.search_tv.return_value = {"title": "My Adventures with Superman", "year": 2023, "id": 125928}
		mock_tmdb1.get_episode_name.return_value = "Guess Who's Slammin' to Dinner"

		mock_tmdb2 = mock_tmdb_services_class.return_value
		mock_tmdb2.search_tv.return_value = {"title": "My Adventures with Superman", "year": 2023, "id": 125928}
		mock_tmdb2.get_episode_name.return_value = "Guess Who's Slammin' to Dinner"

		# 3. Setup Torbox mocks
		mock_torbox = mock_torbox_routes_class.return_value
		mock_torbox.get_torrent_info.return_value = {
			"progress": 1.0,
			"download_speed": 0,
			"download_state": "completed",
			"size": 18,
			"files": [{"id": 1, "name": "My Adventures with Superman S03E04 Guess Whos Slammin to Dinner.mkv", "size": 18}]
		}
		mock_torbox.get_download_link.return_value = "http://example.com/file.mkv"

		# 4. Setup requests.get mock for streaming
		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.iter_content.return_value = [b"mock chunk content"]
		mock_get.return_value = mock_resp

		# 5. Insert queued download
		db_download_id = self.db.execute(
			"INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
			(self.user.id, "torbox_12345", "My Adventures with Superman", "My Adventures with Superman S03E04 Guess Whos Slammin to Dinner.mkv", "magnet:?", "queued", "tv", 0)
		)

		# Ensure directory is clean
		import shutil
		if os.path.exists("./test_library"):
			shutil.rmtree("./test_library")

		# 6. Run background task
		from backend.routes.api import monitor_and_download_task
		monitor_and_download_task(self.user.id, "torbox_12345", {
			'title': 'My Adventures with Superman',
			'filename': 'My Adventures with Superman S03E04 Guess Whos Slammin to Dinner.mkv',
			'magnet': 'magnet:?',
			'category': 'tv',
			'year': 2023,
			'season': 3,
			'episode': 4
		}, db_download_id)

		# 7. Assertions: path and name
		expected_dir = "./test_library/TV SHOWS/My Adventures with Superman (2023) {tmdb-125928}/Season 03"
		expected_file = os.path.join(expected_dir, "My Adventures with Superman (2023) - S03E04 - Guess Who's Slammin' to Dinner.mkv")
		
		self.assertTrue(os.path.exists(expected_dir), "TV show directory with TMDb tag should exist")
		self.assertTrue(os.path.exists(expected_file), "TV show filename without TMDb tag should exist")

		# Now test cancellation deletes the file using the correct prefix
		# We need to re-insert the download into DB as completed first
		db_download_id2 = self.db.execute(
			"INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
			(self.user.id, "torbox_12345", "My Adventures with Superman", "My Adventures with Superman S03E04 Guess Whos Slammin to Dinner.mkv", "magnet:?", "completed", "tv", 18)
		)

		response = self.client.post(
			'/api/torbox/control',
			data=json.dumps({"torbox_id": "torbox_12345", "action": "delete"}),
			content_type='application/json'
		)
		self.assertEqual(response.status_code, 200)
		
		# Verify the file and directory are cleaned up
		self.assertFalse(os.path.exists(expected_file), "TV show episode file should be deleted on cancel")
		self.assertFalse(os.path.exists(expected_dir), "TV show directory should be removed on cancel if empty")

		# Cleanup
		if os.path.exists("./test_library"):
			shutil.rmtree("./test_library")

	@patch('requests.get')
	def test_search_caching(self, mock_get):
		# Clear global search cache before test
		from backend.services.search_cache import global_search_cache
		global_search_cache._query_cache.clear()
		global_search_cache._cards_cache.clear()

		# 1. First search: "John Wick" - hits mock Prowlarr
		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.json.return_value = [
			{
				"title": "John Wick 2014 1080p BluRay",
				"guid": "guid1",
				"size": 1000,
				"indexer": "Indexer",
				"downloadUrl": "magnet:?xt=urn:btih:hash1",
				"infoUrl": "info1",
				"seeders": 50,
				"peers": 5
			},
			{
				"title": "John Wick Chapter 2 2017 1080p BluRay",
				"guid": "guid2",
				"size": 2000,
				"indexer": "Indexer",
				"downloadUrl": "magnet:?xt=urn:btih:hash2",
				"infoUrl": "info2",
				"seeders": 80,
				"peers": 8
			}
		]
		mock_get.return_value = mock_resp

		# Configure server settings with api key
		self.db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", ("prowlarr_api_key", "dummy_prowlarr_key"))

		self.client.set_cookie('session_token', self.token)

		# Run first search
		response = self.client.get('/api/search?q=John+Wick')
		data = json.loads(response.data)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(data['data']), 2) # "John Wick" and "John Wick Chapter 2"
		self.assertEqual(mock_get.call_count, 1)

		# 2. Second search: exact query "John Wick" again - should use exact cache
		# If requests.get is called, raise an error to prove it was bypassed
		mock_get.side_effect = Exception("Should not query external API - exact cache hit expected")
		response2 = self.client.get('/api/search?q=John+Wick')
		data2 = json.loads(response2.data)
		self.assertEqual(response2.status_code, 200)
		self.assertEqual(len(data2['data']), 2)
		
		# 3. Third search: sub-query "John Wick Chapter 2" - should match cached card and bypass Prowlarr
		response3 = self.client.get('/api/search?q=John+Wick+Chapter+2')
		data3 = json.loads(response3.data)
		self.assertEqual(response3.status_code, 200)
		self.assertEqual(len(data3['data']), 1)
		self.assertEqual(data3['data'][0]['clean_title'], "John Wick Chapter 2")

	def test_search_tv_show_magnet_detection(self):
		magnet = "magnet:?xt=urn:btih:B4938B2D9D47CE9947C1B511536E91731BEE57D7&dn=Monsters.The.Lyle.and.Erik.Menendez.Story.S01.COMPLETE.1080p.NF.WEB-DL.H.264-EniaHD&tr=http%3A%2F%2Fbt.t-ru.org%2Fann"
		import urllib.parse
		response = self.client.get(f'/api/search?q={urllib.parse.quote(magnet)}')
		data = json.loads(response.data)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(data['type'], 'search_results')
		self.assertEqual(len(data['data']), 1)
		card = data['data'][0]
		self.assertTrue(card['is_tv'], "Magnet release with S01 should be detected as a TV Show")
		self.assertEqual(card['clean_title'], "Monsters The Lyle and Erik Menendez Story")
		self.assertEqual(card['downloads'][0]['season'], 1)

	def test_torrent_result_tv_parsing(self):
		from backend.models.result import TorrentResult

		tv_cases = [
			("Monsters.The.Lyle.and.Erik.Menendez.Story.S01.COMPLETE.1080p.NF.WEB-DL.H.264-EniaHD", "Monsters The Lyle and Erik Menendez Story", 1, None),
			("Stranger.Things.S04E01.1080p.NF.WEB-DL", "Stranger Things", 4, 1),
			("The.Office.US.1x05.720p.HDTV", "The Office US", 1, 5),
			("Severance.Season.1.1080p.WEB-DL", "Severance", 1, None),
			("House.of.the.Dragon.Ep.02.1080p", "House of the Dragon", None, 2),
			("The.Wire.Complete.Series.720p.BluRay", "The Wire", None, None)
		]
		for title, expected_clean, expected_season, expected_ep in tv_cases:
			tr = TorrentResult(title=title, size=100, download_url="", seeders=0, leechers=0, indexer="")
			self.assertTrue(tr.is_tv, f"Expected {title} to be detected as TV")
			self.assertEqual(tr.clean_title, expected_clean)
			if expected_season is not None:
				self.assertEqual(tr.season, expected_season, f"Expected season {expected_season} for {title}")
			if expected_ep is not None:
				self.assertEqual(tr.episode, expected_ep, f"Expected episode {expected_ep} for {title}")

		movie_cases = [
			("Inception.2010.1080p.BluRay.x264-x0r", "Inception", 2010),
			("Avatar.The.Way.of.Water.2022.2160p.UHD", "Avatar The Way of Water", 2022)
		]
		for title, expected_clean, expected_year in movie_cases:
			tr = TorrentResult(title=title, size=100, download_url="", seeders=0, leechers=0, indexer="")
			self.assertFalse(tr.is_tv, f"Expected {title} to be detected as Movie")
			self.assertEqual(tr.clean_title, expected_clean)
			self.assertEqual(tr.year, expected_year)

	def test_library_sizes_caching_and_invalidation(self):
		import tempfile
		from backend.routes.api import get_library_file_sizes, invalidate_library_sizes_cache
		
		temp_dir = tempfile.mkdtemp(prefix="rico_test_lib_")
		f1 = os.path.join(temp_dir, "file1.mkv")
		with open(f1, "wb") as f:
			f.write(b"0" * 500)

		# Cold scan
		sizes1 = get_library_file_sizes(temp_dir)
		self.assertIn(500, sizes1)

		# Add file without invalidating
		f2 = os.path.join(temp_dir, "file2.mkv")
		with open(f2, "wb") as f:
			f.write(b"0" * 700)

		# Should hit in-memory cache
		sizes2 = get_library_file_sizes(temp_dir)
		self.assertNotIn(700, sizes2)

		# Invalidate and rescan
		invalidate_library_sizes_cache(temp_dir)
		sizes3 = get_library_file_sizes(temp_dir)
		self.assertIn(700, sizes3)

		import shutil
		shutil.rmtree(temp_dir, ignore_errors=True)

	def test_populate_all_cards_downloads_batch(self):
		from backend.routes.api import populate_all_cards_downloads
		
		# Insert dummy download
		self.db.execute(
			"INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
			(self.user.id, "tor_123", "Batch Movie", "batch.mkv", "magnet:?xt=urn:btih:batch123", "completed", "movie", 1024)
		)

		cards = [{
			"clean_title": "Batch Movie",
			"downloads": [
				{"download_url": "magnet:?xt=urn:btih:batch123", "size": 1024},
				{"download_url": "magnet:?xt=urn:btih:other999", "size": 2048}
			]
		}]

		populate_all_cards_downloads(cards, {1024}, self.db)

		self.assertTrue(cards[0]["downloads"][0]["downloaded"])
		self.assertEqual(cards[0]["downloads"][0]["torbox_id"], "tor_123")
		self.assertEqual(cards[0]["downloads"][0]["db_status"], "completed")

		self.assertFalse(cards[0]["downloads"][1]["downloaded"])
		self.assertIsNone(cards[0]["downloads"][1]["torbox_id"])


if __name__ == '__main__':
	unittest.main()

