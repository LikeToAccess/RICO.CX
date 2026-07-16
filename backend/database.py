import sqlite3
import threading
import logging
import json
import os
from typing import Any

logger = logging.getLogger(__name__)

class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        if db_path is None:
            db_path = os.environ.get("DATABASE_PATH", "ricocx.db")
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Database, cls).__new__(cls)
                    cls._instance.db_path = db_path
                    cls._instance._init_db()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            cls._instance = None

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Load schema.sql from the project root folder
        current_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.abspath(os.path.join(current_dir, "../schema.sql"))
        
        if os.path.exists(schema_path):
            try:
                with open(schema_path, "r") as f:
                    schema_sql = f.read()
                    cursor.executescript(schema_sql)
                logger.info(f"Database: Initialized database using schema.sql at {schema_path}")
            except Exception as e:
                logger.error(f"Database: Failed to execute schema.sql: {e}")
        else:
            logger.error(f"Database: schema.sql not found at {schema_path}")
            
        # Run schema migrations dynamically for existing database installations
        try:
            cursor.execute("PRAGMA table_info(users)")
            existing_cols = [row['name'] for row in cursor.fetchall()]
            if existing_cols:
                migrations = [
                    ("full_name", "TEXT"),
                    ("first_name", "TEXT"),
                    ("last_name", "TEXT"),
                    ("profile_picture", "TEXT"),
                    ("created_at", "TIMESTAMP")
                ]
                for col_name, col_type in migrations:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                        logger.info(f"Database: Migrated users table - added column {col_name}")
        except Exception as e:
            logger.error(f"Database: Failed to migrate users table: {e}")

        try:
            cursor.execute("PRAGMA table_info(downloads)")
            existing_cols = [row['name'] for row in cursor.fetchall()]
            if existing_cols:
                migrations = [
                    ("category", "TEXT"),
                    ("created_at", "TIMESTAMP"),
                    ("size", "INTEGER DEFAULT 0")
                ]
                for col_name, col_type in migrations:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE downloads ADD COLUMN {col_name} {col_type}")
                        logger.info(f"Database: Migrated downloads table - added column {col_name}")
        except Exception as e:
            logger.error(f"Database: Failed to migrate downloads table: {e}")

        # Ensure server_settings table exists
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
        except Exception as e:
            logger.error(f"Database: Failed to create server_settings table: {e}")
 
        conn.commit()
        conn.close()

    def query(self, query: str, args: tuple = (), one: bool = False) -> Any:
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(query, args)
            rv = cursor.fetchall()
            conn.commit()
            return (rv[0] if rv else None) if one else rv
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return None
        finally:
            conn.close()

    def execute(self, query: str, args: tuple = ()) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(query, args)
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Database execute error: {e}")
            return -1
        finally:
            conn.close()
