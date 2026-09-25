"""SQLite Database Manager for RICO.CX."""
import logging
import os
import sqlite3
import threading
from typing import Any, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="Database")


class Database:
	"""
	Thread-safe Singleton SQLite Database Manager with WAL mode and high-concurrency connection handling.
	"""
	_instance: Optional["Database"] = None
	_lock = threading.Lock()
	db_path: str

	def __new__(cls: Type[T], db_path: Optional[str] = None) -> T:
		if db_path is None:
			db_path = os.environ.get("DATABASE_PATH", "ricocx.db")
		if cls._instance is None:
			with cls._lock:
				if cls._instance is None:
					instance = super(Database, cls).__new__(cls)
					instance.db_path = db_path
					instance._init_db()
					cls._instance = instance
		return cls._instance  # type: ignore[return-value]

	@classmethod
	def reset_instance(cls) -> None:
		with cls._lock:
			cls._instance = None

	def _get_conn(self) -> sqlite3.Connection:
		conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
		conn.row_factory = sqlite3.Row
		conn.execute("PRAGMA foreign_keys = ON")
		conn.execute("PRAGMA busy_timeout = 30000")
		return conn

	def _init_db(self) -> None:
		conn = self._get_conn()
		cursor = conn.cursor()

		try:
			cursor.execute("PRAGMA journal_mode = WAL")
			cursor.execute("PRAGMA synchronous = NORMAL")
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.warning("Database: Failed to set WAL mode: %s", exc)

		current_dir = os.path.dirname(os.path.abspath(__file__))
		schema_path = os.path.abspath(os.path.join(current_dir, "../schema.sql"))

		if os.path.exists(schema_path):
			try:
				with open(schema_path, "r", encoding="utf-8") as f:
					schema_sql = f.read()
					cursor.executescript(schema_sql)
				logger.info("Database: Initialized database using schema.sql at %s", schema_path)
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Database: Failed to execute schema.sql: %s", exc)
		else:
			logger.error("Database: schema.sql not found at %s", schema_path)

		try:
			cursor.execute("PRAGMA table_info(users)")
			existing_cols = [row['name'] for row in cursor.fetchall()]
			if existing_cols:
				user_migrations = [
					("full_name", "TEXT"),
					("first_name", "TEXT"),
					("last_name", "TEXT"),
					("profile_picture", "TEXT"),
					("created_at", "TIMESTAMP")
				]
				for col_name, col_type in user_migrations:
					if col_name not in existing_cols:
						cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
						logger.info("Database: Migrated users table - added column %s", col_name)
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Database: Failed to migrate users table: %s", exc)

		try:
			cursor.execute("PRAGMA table_info(downloads)")
			existing_cols = [row['name'] for row in cursor.fetchall()]
			if existing_cols:
				download_migrations = [
					("category", "TEXT"),
					("created_at", "TIMESTAMP"),
					("size", "INTEGER DEFAULT 0")
				]
				for col_name, col_type in download_migrations:
					if col_name not in existing_cols:
						cursor.execute(f"ALTER TABLE downloads ADD COLUMN {col_name} {col_type}")
						logger.info("Database: Migrated downloads table - added column %s", col_name)
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Database: Failed to migrate downloads table: %s", exc)

		try:
			cursor.execute("""
				CREATE TABLE IF NOT EXISTS server_settings (
					key TEXT PRIMARY KEY,
					value TEXT
				)
			""")
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Database: Failed to create server_settings table: %s", exc)

		conn.commit()
		conn.close()

	def query(self, sql_query: str, args: Tuple[Any, ...] = (), one: bool = False) -> Any:
		conn = self._get_conn()
		cursor = conn.cursor()
		try:
			cursor.execute(sql_query, args)
			rv = cursor.fetchall()
			return (rv[0] if rv else None) if one else rv
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Database query error: %s", exc)
			return None
		finally:
			conn.close()

	def execute(self, sql_query: str, args: Tuple[Any, ...] = ()) -> int:
		conn = self._get_conn()
		cursor = conn.cursor()
		try:
			cursor.execute(sql_query, args)
			conn.commit()
			return cursor.lastrowid if cursor.lastrowid is not None else -1
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Database execute error: %s", exc)
			return -1
		finally:
			conn.close()
