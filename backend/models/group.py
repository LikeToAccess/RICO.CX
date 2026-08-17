import json
from typing import List, Optional, Type, TypeVar
from ..database import Database

T = TypeVar("T", bound="Group")


class Group:
	"""
	Represents a User Group in the system with specific permissions.
	"""
	def __init__(self, group_id: int, name: str, permissions: Optional[List[str]] = None) -> None:
		self.id = group_id
		self.name = name
		self.permissions = permissions if permissions is not None else []

	@classmethod
	def get_by_id(cls: Type[T], group_id: int) -> Optional[T]:
		db = Database()
		row = db.query("SELECT * FROM groups WHERE id = ?", (group_id,), one=True)
		if row:
			perms = json.loads(row['permissions']) if row['permissions'] else []
			return cls(row['id'], row['name'], perms)
		return None

	@classmethod
	def get_by_name(cls: Type[T], name: str) -> Optional[T]:
		db = Database()
		row = db.query("SELECT * FROM groups WHERE name = ?", (name,), one=True)
		if row:
			perms = json.loads(row['permissions']) if row['permissions'] else []
			return cls(row['id'], row['name'], perms)
		return None

	@classmethod
	def create(cls: Type[T], name: str, permissions: List[str]) -> T:
		db = Database()
		permissions_json = json.dumps(permissions)
		group_id = db.execute("INSERT INTO groups (name, permissions) VALUES (?, ?)", (name, permissions_json))
		return cls(group_id, name, permissions)

	def save(self) -> None:
		db = Database()
		permissions_json = json.dumps(self.permissions)
		db.execute("UPDATE groups SET name = ?, permissions = ? WHERE id = ?", (self.name, permissions_json, self.id))

	def has_permission(self, permission: str) -> bool:
		return permission in self.permissions or "admin" in self.permissions
