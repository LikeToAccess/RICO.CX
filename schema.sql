-- RICO.CX Database Schema

-- 1. Create Groups Table
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    permissions TEXT
);

-- 2. Create Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL, -- Stores Google Email Address
    password_hash TEXT,            -- Retained but randomized for OAuth logins
    group_id INTEGER,
    api_key TEXT,
    settings TEXT,
    full_name TEXT,
    first_name TEXT,
    last_name TEXT,
    profile_picture TEXT,          -- Stores Google Profile Picture URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(group_id) REFERENCES groups(id)
);

-- 3. Create Sessions Table
CREATE TABLE IF NOT EXISTS sessions (
    session_token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 4. Create Downloads Table
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    torbox_id TEXT,
    title TEXT,
    filename TEXT,
    magnet TEXT,
    status TEXT,
    progress REAL DEFAULT 0,
    speed REAL DEFAULT 0,
    size INTEGER DEFAULT 0,
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 5. Create Server Settings Table
CREATE TABLE IF NOT EXISTS server_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 6. Seed Default User Groups
INSERT OR IGNORE INTO groups (id, name, permissions) VALUES (1, 'Admin', '["admin"]');
INSERT OR IGNORE INTO groups (id, name, permissions) VALUES (2, 'User', '["search", "download"]');
INSERT OR IGNORE INTO groups (id, name, permissions) VALUES (3, 'Moderator', '["moderate"]');
