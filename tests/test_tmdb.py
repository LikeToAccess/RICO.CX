import unittest
from unittest.mock import patch, MagicMock
from backend.services.tmdb_client import TmdbClient

class TestTmdbClient(unittest.TestCase):
    @patch('requests.get')
    def test_search_movie(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [{
                "title": "Inception",
                "release_date": "2010-07-16",
                "id": 27205
            }]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = TmdbClient(api_key="test_key")
        res = client.search_movie("Inception", 2010)

        self.assertIsNotNone(res)
        self.assertEqual(res["title"], "Inception")
        self.assertEqual(res["year"], "2010")
        self.assertEqual(res["id"], 27205)

    @patch('requests.get')
    def test_search_tv(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [{
                "name": "Breaking Bad",
                "first_air_date": "2008-01-20",
                "id": 1396
            }]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = TmdbClient(api_key="test_key")
        res = client.search_tv("Breaking Bad", 2008)

        self.assertIsNotNone(res)
        self.assertEqual(res["title"], "Breaking Bad")
        self.assertEqual(res["year"], "2008")
        self.assertEqual(res["id"], 1396)

    @patch('requests.get')
    def test_get_episode_name(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "name": "Pilot"
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = TmdbClient(api_key="test_key")
        res = client.get_episode_name(1396, 1, 1)

        self.assertEqual(res, "Pilot")

if __name__ == '__main__':
    unittest.main()
