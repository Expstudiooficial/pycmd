// PyCmd accounts and Learn progress sync, for pycmd.pages.dev.
//
// The Android and Windows apps never hold a database credential. They talk
// to this handler over HTTPS, and only this handler - running on Cloudflare,
// next to the D1 database bound as `pycmddata1` - talks to the database.
//
//   GET  /api/v1/health                  is the service up, can it reach D1
//   GET  /api/v1/username/<name>         is a username free
//   POST /api/v1/signup   {username, key, device}         -> {token}
//   POST /api/v1/login    {username, key, device}         -> {token}
//   POST /api/v1/logout                                   (signed in)
//   GET  /api/v1/me                                       (signed in)
//   GET  /api/v1/progress                                 (signed in)
//   PUT  /api/v1/progress {data, base_version, device}    (signed in)
//   POST /api/v1/password {old_key, new_key}              (signed in)
//   POST /api/v1/account/delete {key}                     (signed in)
//
// Passwords never reach this server. The app stretches the password with
// PBKDF2-SHA256 (600,000 rounds, salted with the username) and sends the
// result, `key`, as 64 hex digits. This server stretches that again with a
// random salt of its own and keeps only the result. A copy of the database
// therefore holds nothing that signs anybody in, and guessing a password
// from it costs 600,000 rounds a guess, per user. (The second stretch is
// short on purpose: the free plan allows a few milliseconds of CPU per
// request, and the first one already did the slow part.)
//
// Signed-in calls carry `Authorization: Bearer <token>`. A token is 32
// random bytes; only its SHA-256 is stored, so the sessions table cannot be
// replayed either.

export const API_VERSION = 1;

const DAY = 24 * 60 * 60 * 1000;
const SESSION_DAYS = 90;
const SERVER_ROUNDS = 1000;
const MAX_BODY = 400 * 1024;
const MAX_PROGRESS = 300 * 1024;
const USERNAME = /^[A-Za-z0-9](?:[A-Za-z0-9_.-]{1,22})[A-Za-z0-9]$/;
const KEY = /^[0-9a-f]{64}$/;
const RESERVED = new Set([
  "admin", "administrator", "root", "system", "sysadmin", "support", "help",
  "pycmd", "pycmdteam", "official", "staff", "moderator", "mod", "owner",
  "api", "www", "mail", "security", "null", "undefined", "anonymous",
  "expstudio", "expstudiooficial", "claude", "anthropic", "test", "guest",
]);

// Failed sign-ins allowed per window, per username and per address.
const LIMITS = {
  loginUser: { count: 10, window: 15 * 60 * 1000 },
  loginAddress: { count: 40, window: 15 * 60 * 1000 },
  signupAddress: { count: 8, window: 60 * 60 * 1000 },
};

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS pycmd_users (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     username TEXT NOT NULL,
     username_key TEXT NOT NULL UNIQUE,
     salt TEXT NOT NULL,
     hash TEXT NOT NULL,
     kdf TEXT NOT NULL,
     created_at INTEGER NOT NULL,
     password_changed_at INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS pycmd_sessions (
     token_hash TEXT PRIMARY KEY,
     user_id INTEGER NOT NULL,
     device TEXT NOT NULL DEFAULT '',
     created_at INTEGER NOT NULL,
     last_used_at INTEGER NOT NULL,
     expires_at INTEGER NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS pycmd_sessions_user ON pycmd_sessions(user_id)`,
  `CREATE TABLE IF NOT EXISTS pycmd_progress (
     user_id INTEGER PRIMARY KEY,
     data TEXT NOT NULL,
     version INTEGER NOT NULL,
     updated_at INTEGER NOT NULL,
     device TEXT NOT NULL DEFAULT '')`,
  `CREATE TABLE IF NOT EXISTS pycmd_attempts (
     bucket TEXT NOT NULL,
     at INTEGER NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS pycmd_attempts_bucket ON pycmd_attempts(bucket, at)`,
];

let schemaReady = false;

async function ensureSchema(db) {
  if (schemaReady) return;
  await db.batch(SCHEMA.map((sql) => db.prepare(sql)));
  schemaReady = true;
}

// ------------------------------------------------------------------ helpers

const encoder = new TextEncoder();

function hex(bytes) {
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function fromHex(text) {
  const out = new Uint8Array(text.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(text.substr(i * 2, 2), 16);
  return out;
}

function randomBytes(count) {
  const out = new Uint8Array(count);
  crypto.getRandomValues(out);
  return out;
}

function base64url(bytes) {
  let text = "";
  for (const b of bytes) text += String.fromCharCode(b);
  return btoa(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function sha256(text) {
  return hex(await crypto.subtle.digest("SHA-256", encoder.encode(text)));
}

async function stretch(keyHex, saltHex) {
  const material = await crypto.subtle.importKey("raw", fromHex(keyHex), "PBKDF2", false,
    ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: fromHex(saltHex), iterations: SERVER_ROUNDS },
    material, 256);
  return hex(bits);
}

function sameText(a, b) {
  // Constant time for equal lengths, which every stored hash has.
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function reply(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
      ...extra,
    },
  });
}

function fail(status, error, extra = {}) {
  return reply(status, { ok: false, error, ...extra });
}

async function readJson(request) {
  const length = Number(request.headers.get("content-length") || 0);
  if (length > MAX_BODY) return { error: fail(413, "That is too big to send.") };
  let text;
  try {
    text = await request.text();
  } catch {
    return { error: fail(400, "The request could not be read.") };
  }
  if (text.length > MAX_BODY) return { error: fail(413, "That is too big to send.") };
  try {
    const value = JSON.parse(text || "{}");
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    return { value };
  } catch {
    return { error: fail(400, "The request was not JSON.") };
  }
}

function device(value) {
  return String(value || "").replace(/[^\w .()+-]/g, "").slice(0, 40);
}

export function usernameProblem(name) {
  if (typeof name !== "string") return "Pick a username.";
  if (name.length < 3) return "A username has at least 3 characters.";
  if (name.length > 24) return "A username has at most 24 characters.";
  if (!USERNAME.test(name)) {
    return "Use letters, digits, _ . and -, starting and ending with a letter or digit.";
  }
  if (RESERVED.has(name.toLowerCase())) return "That username is reserved. Pick another.";
  return "";
}

function address(request) {
  return request.headers.get("cf-connecting-ip") || request.headers.get("x-real-ip") || "local";
}

async function bucket(kind, value) {
  // Addresses and usernames are kept only as hashes, and only for the window.
  return `${kind}:${(await sha256(`pycmd-limit:${kind}:${value}`)).slice(0, 32)}`;
}

async function overLimit(db, key, limit, now) {
  const row = await db.prepare(
    "SELECT COUNT(*) AS n FROM pycmd_attempts WHERE bucket = ? AND at > ?")
    .bind(key, now - limit.window).first();
  return (row?.n || 0) >= limit.count;
}

async function note(db, keys, now) {
  await db.batch(keys.map((key) =>
    db.prepare("INSERT INTO pycmd_attempts (bucket, at) VALUES (?, ?)").bind(key, now)));
}

async function tidy(db, now) {
  // Now and then, not on every request: old attempts and expired sessions.
  if (Math.random() > 0.02) return;
  await db.batch([
    db.prepare("DELETE FROM pycmd_attempts WHERE at < ?").bind(now - DAY),
    db.prepare("DELETE FROM pycmd_sessions WHERE expires_at < ?").bind(now),
  ]);
}

async function newSession(db, userId, deviceName, now) {
  const token = base64url(randomBytes(32));
  await db.prepare(
    `INSERT INTO pycmd_sessions (token_hash, user_id, device, created_at, last_used_at,
       expires_at) VALUES (?, ?, ?, ?, ?, ?)`)
    .bind(await sha256(token), userId, deviceName, now, now, now + SESSION_DAYS * DAY).run();
  return token;
}

async function signedIn(db, request, now) {
  const header = request.headers.get("authorization") || "";
  const match = header.match(/^Bearer ([A-Za-z0-9_-]{20,100})$/);
  if (!match) return null;
  const tokenHash = await sha256(match[1]);
  const row = await db.prepare(
    `SELECT s.user_id AS id, s.last_used_at AS used, u.username AS username,
            u.salt AS salt, u.hash AS hash, u.created_at AS created
       FROM pycmd_sessions s JOIN pycmd_users u ON u.id = s.user_id
      WHERE s.token_hash = ? AND s.expires_at > ?`)
    .bind(tokenHash, now).first();
  if (!row) return null;
  if (now - row.used > 60 * 60 * 1000) {
    // Sliding expiry, written at most once an hour per session.
    await db.prepare(
      "UPDATE pycmd_sessions SET last_used_at = ?, expires_at = ? WHERE token_hash = ?")
      .bind(now, now + SESSION_DAYS * DAY, tokenHash).run();
  }
  return { ...row, tokenHash };
}

// ----------------------------------------------------------------- handlers

async function health(db) {
  try {
    await ensureSchema(db);
    await db.prepare("SELECT 1 AS one").first();
    return reply(200, { ok: true, service: "pycmd", api: API_VERSION, database: true });
  } catch (error) {
    return reply(503, { ok: false, service: "pycmd", api: API_VERSION, database: false,
      error: "The database is not reachable." });
  }
}

async function username(db, name) {
  const problem = usernameProblem(name);
  if (problem) return reply(200, { ok: true, available: false, reason: problem });
  const row = await db.prepare("SELECT 1 AS taken FROM pycmd_users WHERE username_key = ?")
    .bind(name.toLowerCase()).first();
  return reply(200, row
    ? { ok: true, available: false, reason: "That username is taken. Pick another." }
    : { ok: true, available: true, reason: "" });
}

async function signup(db, request, now) {
  const { value, error } = await readJson(request);
  if (error) return error;
  const name = String(value.username || "").trim();
  const problem = usernameProblem(name);
  if (problem) return fail(400, problem, { field: "username" });
  if (!KEY.test(String(value.key || ""))) {
    return fail(400, "This version of PyCmd cannot sign up. Update the app.");
  }
  const where = await bucket("signup", address(request));
  if (await overLimit(db, where, LIMITS.signupAddress, now)) {
    return fail(429, "Too many new accounts from here. Try again in an hour.");
  }
  await note(db, [where], now);
  const salt = hex(randomBytes(16));
  const hash = await stretch(value.key, salt);
  let userId;
  try {
    const result = await db.prepare(
      `INSERT INTO pycmd_users (username, username_key, salt, hash, kdf, created_at,
         password_changed_at) VALUES (?, ?, ?, ?, ?, ?, ?)`)
      .bind(name, name.toLowerCase(), salt, hash, "pbkdf2-sha256-600000/v1", now, now).run();
    userId = result.meta.last_row_id;
  } catch (failure) {
    // The UNIQUE index is the real check: two sign-ups racing for one name
    // both pass the "is it free" question, and only one insert can win.
    if (String(failure).includes("UNIQUE")) {
      return fail(409, "That username is taken. Pick another.", { field: "username" });
    }
    throw failure;
  }
  const token = await newSession(db, userId, device(value.device), now);
  return reply(201, { ok: true, username: name, token });
}

async function login(db, request, now) {
  const { value, error } = await readJson(request);
  if (error) return error;
  const name = String(value.username || "").trim();
  const key = String(value.key || "");
  const nope = fail(401, "Wrong username or password.");
  if (!name || name.length > 24 || !KEY.test(key)) return nope;
  const byUser = await bucket("login-user", name.toLowerCase());
  const byAddress = await bucket("login-address", address(request));
  if (await overLimit(db, byUser, LIMITS.loginUser, now) ||
      await overLimit(db, byAddress, LIMITS.loginAddress, now)) {
    return fail(429, "Too many wrong passwords. Wait 15 minutes and try again.");
  }
  const user = await db.prepare(
    "SELECT id, username, salt, hash FROM pycmd_users WHERE username_key = ?")
    .bind(name.toLowerCase()).first();
  // A missing user costs the same stretch as a wrong password, so the time a
  // reply takes does not say which usernames exist.
  const hash = await stretch(key, user ? user.salt : "00".repeat(16));
  if (!user || !sameText(hash, user.hash)) {
    await note(db, [byUser, byAddress], now);
    return nope;
  }
  const token = await newSession(db, user.id, device(value.device), now);
  return reply(200, { ok: true, username: user.username, token });
}

async function me(db, who) {
  const row = await db.prepare(
    "SELECT version, updated_at, device FROM pycmd_progress WHERE user_id = ?")
    .bind(who.id).first();
  const sessions = await db.prepare(
    "SELECT COUNT(*) AS n FROM pycmd_sessions WHERE user_id = ?").bind(who.id).first();
  return reply(200, {
    ok: true, username: who.username, created_at: who.created,
    progress: row ? { version: row.version, updated_at: row.updated_at, device: row.device }
      : null,
    sessions: sessions?.n || 0,
  });
}

async function getProgress(db, who) {
  const row = await db.prepare(
    "SELECT data, version, updated_at, device FROM pycmd_progress WHERE user_id = ?")
    .bind(who.id).first();
  if (!row) return reply(200, { ok: true, version: 0, data: null, updated_at: 0, device: "" });
  return reply(200, { ok: true, version: row.version, data: JSON.parse(row.data),
    updated_at: row.updated_at, device: row.device });
}

async function putProgress(db, request, who, now) {
  const { value, error } = await readJson(request);
  if (error) return error;
  const data = value.data;
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return fail(400, "Progress has to be an object.");
  }
  const text = JSON.stringify(data);
  if (text.length > MAX_PROGRESS) return fail(413, "That progress file is too big.");
  const base = Number.isInteger(value.base_version) ? value.base_version : -1;
  const deviceName = device(value.device);
  let result;
  if (base === 0) {
    result = await db.prepare(
      `INSERT INTO pycmd_progress (user_id, data, version, updated_at, device)
       VALUES (?, ?, 1, ?, ?) ON CONFLICT(user_id) DO NOTHING`)
      .bind(who.id, text, now, deviceName).run();
  } else {
    // Only if nobody else wrote since this device last read: otherwise the
    // app merges the newer copy into its own and tries again.
    result = await db.prepare(
      `UPDATE pycmd_progress SET data = ?, version = version + 1, updated_at = ?, device = ?
        WHERE user_id = ? AND version = ?`)
      .bind(text, now, deviceName, who.id, base).run();
  }
  if (!result.meta.changes) {
    const current = await db.prepare(
      "SELECT data, version, updated_at, device FROM pycmd_progress WHERE user_id = ?")
      .bind(who.id).first();
    return reply(409, { ok: false, conflict: true,
      error: "Another device saved first. Merge and try again.",
      version: current ? current.version : 0,
      data: current ? JSON.parse(current.data) : null,
      updated_at: current ? current.updated_at : 0 });
  }
  return reply(200, { ok: true, version: base + 1, updated_at: now });
}

async function changePassword(db, request, who, now) {
  const { value, error } = await readJson(request);
  if (error) return error;
  if (!KEY.test(String(value.old_key || "")) || !KEY.test(String(value.new_key || ""))) {
    return fail(400, "This version of PyCmd cannot change passwords. Update the app.");
  }
  const byUser = await bucket("login-user", who.username.toLowerCase());
  if (await overLimit(db, byUser, LIMITS.loginUser, now)) {
    return fail(429, "Too many wrong passwords. Wait 15 minutes and try again.");
  }
  if (!sameText(await stretch(value.old_key, who.salt), who.hash)) {
    await note(db, [byUser], now);
    return fail(401, "The current password is wrong.");
  }
  const salt = hex(randomBytes(16));
  const hash = await stretch(value.new_key, salt);
  await db.batch([
    db.prepare("UPDATE pycmd_users SET salt = ?, hash = ?, password_changed_at = ? WHERE id = ?")
      .bind(salt, hash, now, who.id),
    // Every other device signs in again with the new password.
    db.prepare("DELETE FROM pycmd_sessions WHERE user_id = ? AND token_hash != ?")
      .bind(who.id, who.tokenHash),
  ]);
  return reply(200, { ok: true });
}

async function deleteAccount(db, request, who, now) {
  const { value, error } = await readJson(request);
  if (error) return error;
  const byUser = await bucket("login-user", who.username.toLowerCase());
  if (await overLimit(db, byUser, LIMITS.loginUser, now)) {
    return fail(429, "Too many wrong passwords. Wait 15 minutes and try again.");
  }
  if (!KEY.test(String(value.key || "")) ||
      !sameText(await stretch(value.key, who.salt), who.hash)) {
    await note(db, [byUser], now);
    return fail(401, "The password is wrong.");
  }
  await db.batch([
    db.prepare("DELETE FROM pycmd_progress WHERE user_id = ?").bind(who.id),
    db.prepare("DELETE FROM pycmd_sessions WHERE user_id = ?").bind(who.id),
    db.prepare("DELETE FROM pycmd_users WHERE id = ?").bind(who.id),
  ]);
  return reply(200, { ok: true });
}

// ------------------------------------------------------------------- router

/**
 * Handles one request under /api/v1/. `path` is what comes after it, e.g.
 * "login" or "username/ana". `db` is the D1 binding (env.pycmddata1).
 */
export async function handle(request, db, path) {
  if (!db) {
    return fail(503, "The PyCmd database is not connected to this site yet.");
  }
  const now = Date.now();
  const method = request.method.toUpperCase();
  const parts = String(path || "").split("/").filter(Boolean);
  const route = parts[0] || "";
  try {
    if (route === "health" && method === "GET") return await health(db);
    await ensureSchema(db);
    await tidy(db, now);
    if (route === "username" && method === "GET" && parts.length === 2) {
      let name = parts[1];
      try {
        name = decodeURIComponent(name);
      } catch {
        // A stray % that is not an escape: check the name as it came.
      }
      return await username(db, name);
    }
    if (route === "signup" && method === "POST") return await signup(db, request, now);
    if (route === "login" && method === "POST") return await login(db, request, now);

    const who = await signedIn(db, request, now);
    const known = ["logout", "me", "progress", "password", "account"];
    if (!known.includes(route)) return fail(404, "There is no such call.");
    if (!who) return fail(401, "Sign in again.", { signed_out: true });

    if (route === "logout" && method === "POST") {
      await db.prepare("DELETE FROM pycmd_sessions WHERE token_hash = ?")
        .bind(who.tokenHash).run();
      return reply(200, { ok: true });
    }
    if (route === "me" && method === "GET") return await me(db, who);
    if (route === "progress" && method === "GET") return await getProgress(db, who);
    if (route === "progress" && method === "PUT") return await putProgress(db, request, who, now);
    if (route === "password" && method === "POST") {
      return await changePassword(db, request, who, now);
    }
    if (route === "account" && parts[1] === "delete" && method === "POST") {
      return await deleteAccount(db, request, who, now);
    }
    return fail(405, "That method is not allowed here.");
  } catch (error) {
    console.error("pycmd api", route, error);
    return fail(500, "Something went wrong on the server. Try again in a minute.");
  }
}

/** For tests: forget that the tables were created. */
export function _resetForTests() {
  schemaReady = false;
}
