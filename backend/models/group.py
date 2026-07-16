import json
from ..database import Database

class Group:
    def __init__(self, id: int, name: str, permissions: list = None):
        self.id = id
        self.name = name
        self.permissions = permissions or []

    @classmethod
    def get_by_id(cls, group_id: int):
        db = Database()
        row = db.query("SELECT * FROM groups WHERE id = ?", (group_id,), one=True)
        if row:
            return cls(row['id'], row['name'], json.loads(row['permissions']) if row['permissions'] else [])
        return None

    @classmethod
    def get_by_name(cls, name: str):
        db = Database()
        row = db.query("SELECT * FROM groups WHERE name = ?", (name,), one=True)
        if row:
            return cls(row['id'], row['name'], json.loads(row['permissions']) if row['permissions'] else [])
        return None

    @classmethod
    def create(cls, name: str, permissions: list):
        db = Database()
        permissions_json = json.dumps(permissions)
        group_id = db.execute("INSERT INTO groups (name, permissions) VALUES (?, ?)", (name, permissions_json))
        return cls(group_id, name, permissions)

    def save(self):
        db = Database()
        permissions_json = json.dumps(self.permissions)
        db.execute("UPDATE groups SET name = ?, permissions = ? WHERE id = ?", (self.name, permissions_json, self.id))

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions or "admin" in self.permissions
