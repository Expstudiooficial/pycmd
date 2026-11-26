# Add PyCmd accounts to pycmd.pages.dev

Hi! I am the owner of PyCmd (the Android and Windows apps) and of this website,
pycmd.pages.dev, which you look after. The apps now have accounts: people sign
up with a username and password, and their PyCmd Learn progress syncs between
the phone and the PC. The apps talk to **this website**, and the website talks
to the database, so the apps never hold a database key. The other assistant who
builds the apps has written and tested the API code; your part is to put it on
the site. Everything you need is below.

## What I want

1. **Keep the website exactly as it is** - pages, design, text, everything.
   Only add what is listed here.
2. **Delete the "disband" sponsor** from the site. You know which one I mean.
   If you are not sure, ask me before you delete anything.
3. **Add the accounts API** (the two files below) so the apps connect to it.
4. Deploy, and check it works (the checks are at the end).

## What is already set up (I did this in the Cloudflare dashboard)

- A D1 database named **`pycmddata1`** (Western Europe), id
  `2e9b84a3-c5b9-4b7e-ae03-3399b068d764`.
- The Pages project **`pycmd`** has a D1 **binding**: variable name
  **`pycmddata1`** → database `pycmddata1` (Settings → Bindings). It takes
  effect on the next deployment. In code it is `context.env.pycmddata1`.
  Please check the binding exists for **Production**, and if you use preview
  deployments, for **Preview** too.
- You do **not** need to create tables. The API creates them itself on the
  first request (`CREATE TABLE IF NOT EXISTS`, all named `pycmd_*`). If you
  prefer, the same SQL is at the end of this message.

## The files to add

Put both at the **root of the Pages project** - next to `package.json` (or the
site's root folder if there is none), **not** inside the build output folder
(`dist/`, `build/`, `public/`, `out/` ...). Cloudflare Pages finds the
`functions/` folder there automatically and deploys it with the site.

```
<project root>/
  functions/api/v1/[[path]].js     <- the route (yes, the file name has the brackets)
  lib/pycmd-api.js                 <- the API itself
```

Notes, depending on how the site is built:

- **Plain static site, Vite, Astro (static), Hugo, etc.**: just add the two
  files as above. Nothing else changes.
- **The project already has a `functions/` folder**: add `api/v1/[[path]].js`
  inside it; keep everything that is there.
- **The project uses `_worker.js` ("advanced mode")**: Pages then ignores the
  `functions/` folder. Instead, import `handle` from `lib/pycmd-api.js` in
  `_worker.js`, and for any request whose path starts with `/api/v1/` return
  `handle(request, env.pycmddata1, pathAfterApiV1)`; send everything else to
  the existing code unchanged.
- **Next.js on Pages / another framework with its own API routes**: keep the
  same URLs (`/api/v1/...`) and call `handle(request, env.pycmddata1, path)`
  from a catch-all route.
- If something already answers `/api/v1/...` on the site, tell me before
  changing it.

### `functions/api/v1/[[path]].js`

```js
// Cloudflare Pages Function: every request under /api/v1/ goes to the PyCmd
// accounts handler. The D1 database is bound to the Pages project as
// `pycmddata1` (Settings -> Bindings), so it arrives here as env.pycmddata1.
import { handle } from "../../../lib/pycmd-api.js";

export async function onRequest(context) {
  const path = Array.isArray(context.params.path)
    ? context.params.path.join("/")
    : String(context.params.path || "");
  return handle(context.request, context.env.pycmddata1, path);
}
```

### `lib/pycmd-api.js`

```js
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
// Cloud storage: what each account may keep, in bytes before compression.
export const QUOTA = 800 * 1024;
const MAX_FILES = 500;
const MAX_FILE_BODY = 1200 * 1024;  // 800 KB as base64, with room for the JSON
const FILE_PATH = /^(?!\/)(?!.*\.\.)[A-Za-z0-9 _.\-\/]{1,200}$/;
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
  `CREATE TABLE IF NOT EXISTS pycmd_files (
     user_id INTEGER NOT NULL,
     path TEXT NOT NULL,
     data TEXT NOT NULL,
     size INTEGER NOT NULL,
     updated_at INTEGER NOT NULL,
     PRIMARY KEY (user_id, path))`,
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

// Stored compressed: Learn progress is long lists of lesson ids, which gzip
// shrinks about tenfold, and the database is 500 MB for everybody. Rows
// written before this are plain JSON and still read.
function b64(bytes) {
  let text = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(text);
}

function unb64(text) {
  const raw = atob(text);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function gzip(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function gunzip(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function pack(text) {
  return "gz:" + b64(await gzip(encoder.encode(text)));
}

export async function unpack(stored) {
  if (!String(stored).startsWith("gz:")) return stored;
  return new TextDecoder().decode(await gunzip(unb64(stored.slice(3))));
}

async function readJson(request, max = MAX_BODY) {
  const length = Number(request.headers.get("content-length") || 0);
  if (length > max) return { error: fail(413, "That is too big to send.") };
  let text;
  try {
    text = await request.text();
  } catch {
    return { error: fail(400, "The request could not be read.") };
  }
  if (text.length > max) return { error: fail(413, "That is too big to send.") };
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
  const used = await storageUsed(db, who.id);
  return reply(200, {
    ok: true, username: who.username, created_at: who.created,
    progress: row ? { version: row.version, updated_at: row.updated_at, device: row.device }
      : null,
    sessions: sessions?.n || 0,
    storage: { used, quota: QUOTA },
  });
}

async function getProgress(db, who) {
  const row = await db.prepare(
    "SELECT data, version, updated_at, device FROM pycmd_progress WHERE user_id = ?")
    .bind(who.id).first();
  if (!row) return reply(200, { ok: true, version: 0, data: null, updated_at: 0, device: "" });
  return reply(200, { ok: true, version: row.version, data: JSON.parse(await unpack(row.data)),
    updated_at: row.updated_at, device: row.device });
}

async function putProgress(db, request, who, now) {
  const { value, error } = await readJson(request);
  if (error) return error;
  const data = value.data;
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return fail(400, "Progress has to be an object.");
  }
  const plain = JSON.stringify(data);
  if (plain.length > MAX_PROGRESS) return fail(413, "That progress file is too big.");
  const text = await pack(plain);
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
      data: current ? JSON.parse(await unpack(current.data)) : null,
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
    db.prepare("DELETE FROM pycmd_files WHERE user_id = ?").bind(who.id),
    db.prepare("DELETE FROM pycmd_sessions WHERE user_id = ?").bind(who.id),
    db.prepare("DELETE FROM pycmd_users WHERE id = ?").bind(who.id),
  ]);
  return reply(200, { ok: true });
}

// ----------------------------------------------------------- cloud storage

async function storageUsed(db, userId) {
  const row = await db.prepare(
    "SELECT COALESCE(SUM(size), 0) AS used, COUNT(*) AS n FROM pycmd_files WHERE user_id = ?")
    .bind(userId).first();
  return row?.used || 0;
}

function filePath(raw) {
  let path;
  try {
    path = decodeURIComponent(raw);
  } catch {
    path = raw;
  }
  return FILE_PATH.test(path) ? path : "";
}

async function listFiles(db, who) {
  const rows = await db.prepare(
    "SELECT path, size, updated_at FROM pycmd_files WHERE user_id = ? ORDER BY path")
    .bind(who.id).all();
  const files = rows.results || [];
  return reply(200, { ok: true, files, used: files.reduce((n, f) => n + f.size, 0),
    quota: QUOTA });
}

async function getFile(db, who, path) {
  const row = await db.prepare(
    "SELECT data, size, updated_at FROM pycmd_files WHERE user_id = ? AND path = ?")
    .bind(who.id, path).first();
  if (!row) return fail(404, "There is no such file in your cloud storage.");
  const bytes = await gunzip(unb64(row.data));
  return reply(200, { ok: true, path, size: row.size, updated_at: row.updated_at,
    content_b64: b64(bytes) });
}

async function putFile(db, request, who, path, now) {
  const { value, error } = await readJson(request, MAX_FILE_BODY);
  if (error) return error;
  let bytes;
  try {
    bytes = unb64(String(value.content_b64 || ""));
  } catch {
    return fail(400, "content_b64 has to be base64.");
  }
  const old = await db.prepare(
    "SELECT size FROM pycmd_files WHERE user_id = ? AND path = ?").bind(who.id, path).first();
  const count = await db.prepare(
    "SELECT COUNT(*) AS n FROM pycmd_files WHERE user_id = ?").bind(who.id).first();
  if (!old && (count?.n || 0) >= MAX_FILES) {
    return fail(413, `Cloud storage holds at most ${MAX_FILES} files.`);
  }
  const used = await storageUsed(db, who.id) - (old ? old.size : 0);
  if (used + bytes.length > QUOTA) {
    return fail(413, `That does not fit: ${Math.ceil((QUOTA - used) / 1024)} KB of your `
      + `${QUOTA / 1024} KB is free, and the file is ${Math.ceil(bytes.length / 1024)} KB.`,
    { used, quota: QUOTA });
  }
  await db.prepare(
    `INSERT INTO pycmd_files (user_id, path, data, size, updated_at) VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(user_id, path) DO UPDATE SET data = excluded.data, size = excluded.size,
       updated_at = excluded.updated_at`)
    .bind(who.id, path, b64(await gzip(bytes)), bytes.length, now).run();
  return reply(200, { ok: true, path, size: bytes.length, used: used + bytes.length,
    quota: QUOTA });
}

async function deleteFile(db, who, path) {
  const result = await db.prepare("DELETE FROM pycmd_files WHERE user_id = ? AND path = ?")
    .bind(who.id, path).run();
  if (!result.meta.changes) return fail(404, "There is no such file in your cloud storage.");
  return reply(200, { ok: true, used: await storageUsed(db, who.id), quota: QUOTA });
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
    const known = ["logout", "me", "progress", "password", "account", "files"];
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
    if (route === "files") {
      if (parts.length === 1 && method === "GET") return await listFiles(db, who);
      const path = filePath(parts.slice(1).join("/"));
      if (!path) {
        return fail(400, "A file name is 1-200 letters, digits, spaces and _ . - /, "
          + "with no .. in it.");
      }
      if (method === "GET") return await getFile(db, who, path);
      if (method === "PUT") return await putFile(db, request, who, path, now);
      if (method === "DELETE") return await deleteFile(db, who, path);
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
```

## Rules - please do not change these

The apps are already built against this exact API, so:

- Keep the URLs (`/api/v1/...`), the JSON field names, the status codes and
  the binding name `pycmddata1`.
- Do not change the password key scheme. The apps send `key` = PBKDF2-SHA256
  of the password (NFC), salt `"pycmd-account-v1:" + username.toLowerCase()`,
  600,000 rounds, 32 bytes, lower-case hex. Test vector: username `Tester`,
  password `correct horse staple` →
  `423ab8b3a7d9d795774e1b8986a53c2ecc9f3cf41f73899a09d46571da0076d8`.
- Do not add CORS headers (`Access-Control-Allow-Origin`). The apps are not
  browsers, and without CORS no other website can call the API from someone's
  browser.
- Do not log request bodies, passwords, keys or tokens. The handler logs only
  the route name and the error on a crash.
- Do not add any endpoint that lists users or reads someone else's data.

## Optional: sign-in on the website itself

Not needed now. If I ask for it later: a page on this site can call the same
API (same origin, so no CORS needed) - but it must make `key` exactly as above
in the browser with WebCrypto and never send the password itself:

```js
async function pycmdKey(username, password) {
  const text = new TextEncoder();
  const material = await crypto.subtle.importKey(
    "raw", text.encode(password.normalize("NFC")), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", iterations: 600000,
      salt: text.encode("pycmd-account-v1:" + username.trim().toLowerCase()) },
    material, 256);
  return [...new Uint8Array(bits)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
```

Keep the token it gets back in `sessionStorage` (not `localStorage`), and send
it as `Authorization: Bearer <token>`.

## Check it after deploying

1. `https://pycmd.pages.dev/api/v1/health` should return
   `{"ok":true,"service":"pycmd","api":1,"database":true}`.
   - `503` with "not connected" means the binding is missing or the site was
     not redeployed after adding it.
   - `404` means the `functions/` folder is not at the project root (or the
     project uses `_worker.js` - see above).
2. `https://pycmd.pages.dev/api/v1/username/someone` should return
   `{"ok":true,"available":true,"reason":""}`.
3. `https://pycmd.pages.dev/api/v1/username/admin` should say it is reserved.
4. A sign-up and sign-in round trip, with the test vector as the key:

```sh
curl -s -X POST https://pycmd.pages.dev/api/v1/signup \
  -H 'content-type: application/json' \
  -d '{"username":"pycmd-check","key":"423ab8b3a7d9d795774e1b8986a53c2ecc9f3cf41f73899a09d46571da0076d8","device":"curl"}'
# -> {"ok":true,"username":"pycmd-check","token":"..."}

curl -s -X POST https://pycmd.pages.dev/api/v1/login \
  -H 'content-type: application/json' \
  -d '{"username":"pycmd-check","key":"423ab8b3a7d9d795774e1b8986a53c2ecc9f3cf41f73899a09d46571da0076d8","device":"curl"}'
# -> {"ok":true,...}  (a different key -> 401 "Wrong username or password.")

# Then delete the test account again (use the token from the login):
curl -s -X POST https://pycmd.pages.dev/api/v1/account/delete \
  -H 'content-type: application/json' -H 'authorization: Bearer <token>' \
  -d '{"key":"423ab8b3a7d9d795774e1b8986a53c2ecc9f3cf41f73899a09d46571da0076d8"}'
# -> {"ok":true}
```

5. The rest of the site still looks and works exactly as before, and the
   "disband" sponsor is gone.

When you are done, tell me what `/api/v1/health` returns, and anything you had
to do differently from the steps above.

## The tables (for reference only - the API creates them)

```sql
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
```
