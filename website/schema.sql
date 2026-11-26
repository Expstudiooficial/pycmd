-- PyCmd accounts, for the D1 database bound as pycmddata1.
-- You do not have to run this: lib/pycmd-api.js creates the same tables
-- itself on the first request. It is here for anyone who prefers:
--   npx wrangler d1 execute pycmddata1 --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS pycmd_users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  username_key TEXT NOT NULL UNIQUE,
  salt TEXT NOT NULL,
  hash TEXT NOT NULL,
  kdf TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  password_changed_at INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS pycmd_sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  device TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  last_used_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL);

CREATE INDEX IF NOT EXISTS pycmd_sessions_user ON pycmd_sessions(user_id);

CREATE TABLE IF NOT EXISTS pycmd_progress (
  user_id INTEGER PRIMARY KEY,
  data TEXT NOT NULL,
  version INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  device TEXT NOT NULL DEFAULT '');

CREATE TABLE IF NOT EXISTS pycmd_attempts (
  bucket TEXT NOT NULL,
  at INTEGER NOT NULL);

CREATE INDEX IF NOT EXISTS pycmd_attempts_bucket ON pycmd_attempts(bucket, at);
