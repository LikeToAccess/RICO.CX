import unittest
from unittest.mock import patch, MagicMock
import os
import json
from backend.app import create_app
from backend.database import Database
from backend.models.user import User

class TestAuth(unittest.TestCase):
    def setUp(self):
        # Configure DATABASE_PATH to isolate database tests
        self.db_path = "test_auth_ricocx.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.environ["DATABASE_PATH"] = self.db_path
        
        # Reset Database class singleton instance
        Database.reset_instance()
        
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        self.db = Database()

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

    def test_user_creation_and_fields(self):
        user = User.create(
            username="test@example.com",
            password="somepassword",
            group_name="User",
            full_name="Test User",
            first_name="Test",
            last_name="User",
            profile_picture="https://example.com/avatar.jpg"
        )
        
        self.assertIsNotNone(user.id)
        self.assertEqual(user.username, "test@example.com")
        self.assertEqual(user.full_name, "Test User")
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")
        self.assertEqual(user.profile_picture, "https://example.com/avatar.jpg")
        
        # Test get_by_id
        fetched = User.get_by_id(user.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.username, "test@example.com")
        self.assertEqual(fetched.full_name, "Test User")
        
        # Test get_by_username
        fetched_uname = User.get_by_username("test@example.com")
        self.assertIsNotNone(fetched_uname)
        self.assertEqual(fetched_uname.id, user.id)

    def test_user_sessions(self):
        user = User.create(
            username="session@example.com",
            password="password123",
            group_name="User"
        )
        
        # Create session
        token = User.create_session(user.id)
        self.assertIsNotNone(token)
        
        # Verify session
        verified_user = User.verify_session(token)
        self.assertIsNotNone(verified_user)
        self.assertEqual(verified_user.id, user.id)
        
        # Delete session
        User.delete_session(token)
        
        # Verify deleted session returns None
        verified_user = User.verify_session(token)
        self.assertIsNone(verified_user)

    def test_auth_me_unauthorized(self):
        # GET /api/auth/me without token should return 401
        response = self.client.get('/api/auth/me')
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertEqual(data["error"], "Unauthorized")

    def test_auth_me_authorized(self):
        user = User.create(
            username="me@example.com",
            password="mypassword",
            group_name="User",
            full_name="Me User"
        )
        token = User.create_session(user.id)
        
        # Request with session_token in cookie
        self.client.set_cookie('session_token', token)
        response = self.client.get('/api/auth/me')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["username"], "me@example.com")
        self.assertEqual(data["full_name"], "Me User")

        # Request with session_token in Authorization header
        self.client.delete_cookie('session_token')
        response = self.client.get('/api/auth/me', headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)

    @patch('requests.post')
    @patch('requests.get')
    def test_google_callback_new_admin_user(self, mock_get, mock_post):
        # Mock Google Token Exchange
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "mock_google_access_token"}
        mock_post.return_value = mock_token_resp
        
        # Mock Google Userinfo
        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.status_code = 200
        mock_userinfo_resp.json.return_value = {
            "email": "admin@example.com",
            "name": "Admin User",
            "given_name": "Admin",
            "family_name": "User",
            "picture": "https://google.com/admin.jpg"
        }
        mock_get.return_value = mock_userinfo_resp
        
        response = self.client.get('/api/auth/google/callback?code=mock_code')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/')
        
        # The first user created should be "Admin" role
        admin_user = User.get_by_username("admin@example.com")
        self.assertIsNotNone(admin_user)
        self.assertEqual(admin_user.full_name, "Admin User")
        self.assertEqual(admin_user.group.name, "Admin")
        
        # Verify session token cookie is set
        cookie = self.client.get_cookie('session_token')
        self.assertIsNotNone(cookie)
        
        # Verify it's a valid session
        verified = User.verify_session(cookie.value)
        self.assertIsNotNone(verified)
        self.assertEqual(verified.id, admin_user.id)

    @patch('requests.post')
    @patch('requests.get')
    def test_google_callback_existing_user_update(self, mock_get, mock_post):
        # Create an existing user first
        existing_user = User.create(
            username="user@example.com",
            password="random_password",
            group_name="User",
            full_name="Old Name",
            profile_picture="https://google.com/old.jpg"
        )
        
        # Mock Google Token Exchange
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "mock_google_access_token"}
        mock_post.return_value = mock_token_resp
        
        # Mock Google Userinfo returns new name and picture
        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.status_code = 200
        mock_userinfo_resp.json.return_value = {
            "email": "user@example.com",
            "name": "New Name",
            "given_name": "New",
            "family_name": "Name",
            "picture": "https://google.com/new.jpg"
        }
        mock_get.return_value = mock_userinfo_resp
        
        response = self.client.get('/api/auth/google/callback?code=mock_code')
        self.assertEqual(response.status_code, 302)
        
        # User details should be updated
        updated_user = User.get_by_username("user@example.com")
        self.assertEqual(updated_user.full_name, "New Name")
        self.assertEqual(updated_user.profile_picture, "https://google.com/new.jpg")
        
        # Verify it's still "User" group (wasn't changed to Admin)
        self.assertEqual(updated_user.group.name, "User")

if __name__ == '__main__':
    unittest.main()
