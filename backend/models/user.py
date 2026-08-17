import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Type, TypeVar
from werkzeug.security import check_password_hash, generate_password_hash
from ..database import Database
from .group import Group

T = TypeVar("T", bound="User")


class User:
	"""
	Represents a User in the system with authentication, authorization, and session management.
	"""
	def __init__(
		self,
		user_id: int,
		username: str,
		password_hash: str,
		group_id: Optional[int],
		api_key: Optional[str] = None,
		settings: Optional[Dict[str, Any]] = None,
		full_name: Optional[str] = None,
		first_name: Optional[str] = None,
		last_name: Optional[str] = None,
		profile_picture: Optional[str] = None,
		created_at: Optional[str] = None
	) -> None:
		self.id = user_id
		self.username = username
		self.password_hash = password_hash
		self.group_id = group_id
		self.api_key = api_key
		self.settings = settings if settings is not None else {}
		self.full_name = full_name
		self.first_name = first_name
		self.last_name = last_name
		self.profile_picture = profile_picture
		self.created_at = created_at

	@property
	def group(self) -> Optional[Group]:
		if self.group_id is None:
			return None
		return Group.get_by_id(self.group_id)

	@classmethod
	def get_by_id(cls: Type[T], user_id: int) -> Optional[T]:
		db = Database()
		row = db.query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
		if row:
			keys = row.keys()
			return cls(
				user_id=row['id'],
				username=row['username'],
				password_hash=row['password_hash'],
				group_id=row['group_id'],
				api_key=row['api_key'] if 'api_key' in keys else None,
				settings=json.loads(row['settings']) if 'settings' in keys and row['settings'] else {},
				full_name=row['full_name'] if 'full_name' in keys else None,
				first_name=row['first_name'] if 'first_name' in keys else None,
				last_name=row['last_name'] if 'last_name' in keys else None,
				profile_picture=row['profile_picture'] if 'profile_picture' in keys else None,
				created_at=row['created_at'] if 'created_at' in keys else None
			)
		return None

	@classmethod
	def get_by_username(cls: Type[T], username: str) -> Optional[T]:
		db = Database()
		row = db.query("SELECT * FROM users WHERE username = ?", (username,), one=True)
		if row:
			keys = row.keys()
			return cls(
				user_id=row['id'],
				username=row['username'],
				password_hash=row['password_hash'],
				group_id=row['group_id'],
				api_key=row['api_key'] if 'api_key' in keys else None,
				settings=json.loads(row['settings']) if 'settings' in keys and row['settings'] else {},
				full_name=row['full_name'] if 'full_name' in keys else None,
				first_name=row['first_name'] if 'first_name' in keys else None,
				last_name=row['last_name'] if 'last_name' in keys else None,
				profile_picture=row['profile_picture'] if 'profile_picture' in keys else None,
				created_at=row['created_at'] if 'created_at' in keys else None
			)
		return None

	@classmethod
	def create(
		cls: Type[T],
		username: str,
		password: str,
		group_name: Optional[str] = "User",
		api_key: Optional[str] = None,
		full_name: Optional[str] = None,
		first_name: Optional[str] = None,
		last_name: Optional[str] = None,
		profile_picture: Optional[str] = None
	) -> T:
		db = Database()

		group = None
		if group_name is not None:
			group = Group.get_by_name(group_name)
			if not group:
				if group_name == "Admin":
					group = Group.create("Admin", ["admin"])
				elif group_name == "Moderator":
					group = Group.create("Moderator", ["moderate"])
				else:
					group = Group.create("User", ["search", "download"])

		password_hash = generate_password_hash(password)
		settings_json = json.dumps({})

		group_id = group.id if group else None

		user_id = db.execute(
			"""INSERT INTO users 
			   (username, password_hash, group_id, api_key, settings, full_name, first_name, last_name, profile_picture) 
			   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
			(username, password_hash, group_id, api_key, settings_json, full_name, first_name, last_name, profile_picture)
		)

		user_row = db.query("SELECT created_at FROM users WHERE id = ?", (user_id,), one=True)
		created_at = user_row['created_at'] if user_row else None

		return cls(
			user_id=user_id,
			username=username,
			password_hash=password_hash,
			group_id=group_id,
			api_key=api_key,
			settings={},
			full_name=full_name,
			first_name=first_name,
			last_name=last_name,
			profile_picture=profile_picture,
			created_at=created_at
		)

	def verify_password(self, password: str) -> bool:
		if not self.password_hash:
			return False
		return check_password_hash(self.password_hash, password)

	def save(self) -> None:
		db = Database()
		settings_json = json.dumps(self.settings)
		row = db.query("SELECT * FROM users LIMIT 1", one=True)
		keys = row.keys() if row else []

		if 'full_name' in keys:
			db.execute(
				"""UPDATE users SET 
				   username = ?, password_hash = ?, group_id = ?, api_key = ?, settings = ?, 
				   full_name = ?, first_name = ?, last_name = ?, profile_picture = ? 
				   WHERE id = ?""",
				(self.username, self.password_hash, self.group_id, self.api_key, settings_json,
				 self.full_name, self.first_name, self.last_name, self.profile_picture, self.id)
			)
		else:
			db.execute(
				"""UPDATE users SET 
				   username = ?, password_hash = ?, group_id = ?, api_key = ?, settings = ? 
				   WHERE id = ?""",
				(self.username, self.password_hash, self.group_id, self.api_key, settings_json, self.id)
			)

	def has_permission(self, permission: str) -> bool:
		grp = self.group
		if grp:
			return grp.has_permission(permission)
		return False

	@classmethod
	def create_session(cls, user_id: int, days_valid: int = 30) -> str:
		db = Database()
		token = secrets.token_hex(32)
		now_dt = datetime.now(timezone.utc)
		expires_at = now_dt + timedelta(days=days_valid)
		expires_str = expires_at.isoformat()

		db.execute("DELETE FROM sessions WHERE expires_at < ?", (now_dt.isoformat(),))

		db.execute(
			"INSERT INTO sessions (session_token, user_id, expires_at) VALUES (?, ?, ?)",
			(token, user_id, expires_str)
		)
		return token

	@classmethod
	def verify_session(cls: Type[T], token: Optional[str]) -> Optional[T]:
		if not token:
			return None
		db = Database()
		now_str = datetime.now(timezone.utc).isoformat()
		row = db.query(
			"SELECT user_id FROM sessions WHERE session_token = ? AND expires_at > ?",
			(token, now_str),
			one=True
		)
		if row:
			return cls.get_by_id(row['user_id'])
		return None

	@classmethod
	def delete_session(cls, token: Optional[str]) -> None:
		if not token:
			return
		db = Database()
		db.execute("DELETE FROM sessions WHERE session_token = ?", (token,))

	def to_dict(self) -> Dict[str, Any]:
		return {
			"id": self.id,
			"username": self.username,
			"group_id": self.group_id,
			"group_name": self.group.name if self.group else None,
			"api_key": self.api_key,
			"settings": self.settings,
			"full_name": self.full_name,
			"first_name": self.first_name,
			"last_name": self.last_name,
			"profile_picture": self.profile_picture,
			"created_at": self.created_at
		}
