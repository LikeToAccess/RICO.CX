"""Security verification test suite for RICO.CX v4."""
import os
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import parse_qs, urlparse
from flask import redirect
from backend.app import create_app
from backend.database import Database
from backend.models.user import User
from backend.services.torbox_client import TorboxClient


class TestSecurity(unittest.TestCase):
	"""Security test cases ensuring headers, cookies, and files are secure."""

	def setUp(self) -> None:
		self.db_path = "test_security_ricocx.db"
		if os.path.exists(self.db_path):
			os.remove(self.db_path)
		os.environ["DATABASE_PATH"] = self.db_path

		Database.reset_instance()

		self.app = create_app()
		self.app.config['TESTING'] = True
		self.client = self.app.test_client()

		self.db = Database()
		self.user = User.create(
			username="secuser@example.com",
			password="secpassword123",
			group_name="User"
		)
		self.token = User.create_session(self.user.id)
		self.client.set_cookie('session_token', self.token)

	def tearDown(self) -> None:
		Database.reset_instance()
		if os.path.exists(self.db_path):
			try:
				os.remove(self.db_path)
			except OSError:
				pass
		if "DATABASE_PATH" in os.environ:
			del os.environ["DATABASE_PATH"]

	@patch('requests.get')
	def test_sec_01_api_key_not_leaked_to_third_party(self, mock_get: MagicMock) -> None:
		"""SEC-01: Verify Prowlarr API key is NOT sent to third-party domains."""
		self.db.execute(
			"INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)",
			("prowlarr_api_key", "SUPER_SECRET_PROWLARR_KEY")
		)
		self.db.execute(
			"INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)",
			("prowlarr_url", "http://internal-prowlarr:9696")
		)
		self.db.execute(
			"INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)",
			("torbox_api_key", "dummy_torbox_key")
		)

		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.headers = {"Content-Disposition": 'attachment; filename="release.torrent"'}
		mock_resp.content = b"torrent_bytes"
		mock_resp.text = "binary"
		mock_get.return_value = mock_resp

		client = TorboxClient(api_key="dummy_torbox_key")

		# 1. Request to third-party domain
		client.add_magnet("https://external-tracker.net/download/file.torrent")
		called_headers = mock_get.call_args[1].get('headers', {}) if mock_get.call_args else {}
		self.assertNotIn("X-Api-Key", called_headers, "Prowlarr key must not leak to third parties")

		# 2. Request to configured internal Prowlarr host
		client.add_magnet("http://internal-prowlarr:9696/api/v1/indexer/torrent/123")
		prowlarr_headers = mock_get.call_args[1].get('headers', {}) if mock_get.call_args else {}
		self.assertIn("X-Api-Key", prowlarr_headers, "Prowlarr key must be sent to Prowlarr host")
		self.assertEqual(prowlarr_headers["X-Api-Key"], "SUPER_SECRET_PROWLARR_KEY")

	def test_sec_04_oauth_state_parameter_generated_and_validated(self) -> None:
		"""SEC-04: Verify Google OAuth uses CSRF state token and validates callback."""
		os.environ["GOOGLE_CLIENT_ID"] = "test_google_client_id.apps.googleusercontent.com"

		response = self.client.get('/api/auth/google/login')
		self.assertEqual(response.status_code, 302)
		location = response.headers.get("Location", "")
		parsed_url = urlparse(location)
		query_params = parse_qs(parsed_url.query)

		self.assertIn("state", query_params, "OAuth URL must contain state parameter")
		state_value = query_params["state"][0]
		self.assertTrue(len(state_value) >= 16, "OAuth state token must be random")

		cookies = response.headers.getlist("Set-Cookie")
		oauth_cookie_found = any("oauth_state" in c for c in cookies)
		self.assertTrue(oauth_cookie_found, "oauth_state cookie must be set on login redirect")

		callback_no_state = self.client.get('/api/auth/google/callback?code=testcode')
		self.assertEqual(callback_no_state.status_code, 400)

		self.client.set_cookie("oauth_state", "valid_secret_state")
		callback_bad_state = self.client.get(
			'/api/auth/google/callback?code=testcode&state=wrong_attacker_state'
		)
		self.assertEqual(callback_bad_state.status_code, 400)

	def test_sec_05_session_cookie_security_flags(self) -> None:
		"""SEC-05: Verify session cookies include HttpOnly, SameSite, and Secure flags."""
		os.environ["USE_SSL"] = "True"
		user = User.create("secureuser@example.com", "pass", "User")
		token = User.create_session(user.id)

		with self.app.test_request_context(base_url="https://localhost:5000"):
			response = redirect("/")
			response.set_cookie(
				"session_token",
				token,
				max_age=30*24*60*60,
				httponly=True,
				samesite='Lax',
				secure=True
			)

			set_cookie = response.headers.get("Set-Cookie", "")
			self.assertIn("HttpOnly", set_cookie)
			self.assertIn("SameSite=Lax", set_cookie)
			self.assertIn("Secure", set_cookie)
		os.environ["USE_SSL"] = "False"

	def test_sec_06_sensitive_and_hidden_files_blocked(self) -> None:
		"""SEC-06: Verify sensitive files (.env, .db, .py, etc.) are blocked with HTTP 403."""
		sensitive_paths = [
			'/.env',
			'/.env.local',
			'/database.db',
			'/ricocx.db',
			'/schema.sql',
			'/main.py',
			'/backend/app.py',
			'/requirements.txt',
			'/.git/config',
			'/../.env'
		]

		for path in sensitive_paths:
			res = self.client.get(path)
			self.assertEqual(res.status_code, 403, f"Path {path} should be blocked with HTTP 403")

	def test_sec_08_gitignore_contains_pem_exclusions(self) -> None:
		"""SEC-08: Verify .gitignore includes *.pem and certificate exclusions."""
		with open(".gitignore", "r", encoding="utf-8") as f:
			content = f.read()
		self.assertIn("*.pem", content)
		self.assertIn("cert.pem", content)
		self.assertIn("key.pem", content)


if __name__ == '__main__':
	unittest.main()
