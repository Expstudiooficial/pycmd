// node --test website/test/   (Node 22+)
//
// The accounts handler against a real SQLite database, through the same
// Request/Response objects Cloudflare uses.
import assert from "node:assert/strict";
import { test } from "node:test";
import { D1 } from "./d1-shim.mjs";
import { handle, usernameProblem, _resetForTests } from "../lib/pycmd-api.js";

const BASE = "https://pycmd.pages.dev/api/v1/";

function freshDb() {
  _resetForTests();
  return new D1();
}

async function call(db, method, path, body, { token, ip = "1.2.3.4" } = {}) {
  const headers = { "content-type": "application/json", "cf-connecting-ip": ip };
  if (token) headers.authorization = `Bearer ${token}`;
  const request = new Request(BASE + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  const response = await handle(request, db, path);
  return { status: response.status, body: await response.json(), headers: response.headers };
}

const KEY_A = "a".repeat(64);
const KEY_B = "b".repeat(64);

test("health says the database is there", async () => {
  const db = freshDb();
  const r = await call(db, "GET", "health");
  assert.equal(r.status, 200);
  assert.equal(r.body.database, true);
  assert.equal(r.headers.get("cache-control"), "no-store");
});

test("no binding is a clear 503, not a crash", async () => {
  const r = await handle(new Request(BASE + "health"), undefined, "health");
  assert.equal(r.status, 503);
  assert.match((await r.json()).error, /not connected/);
});

test("usernames: rules, reserved names, case", () => {
  assert.equal(usernameProblem("ana"), "");
  assert.equal(usernameProblem("Ana_99.dev"), "");
  assert.match(usernameProblem("ab"), /at least 3/);
  assert.match(usernameProblem("x".repeat(25)), /at most 24/);
  assert.match(usernameProblem("-ana"), /starting and ending/);
  assert.match(usernameProblem("ana-"), /starting and ending/);
  assert.match(usernameProblem("an a"), /Use letters/);
  assert.match(usernameProblem("ána"), /Use letters/);
  assert.match(usernameProblem("Admin"), /reserved/);
  assert.match(usernameProblem("PyCmd"), /reserved/);
});

test("sign up, then the same name in any case is taken", async () => {
  const db = freshDb();
  let r = await call(db, "GET", "username/Ana");
  assert.deepEqual([r.body.available, r.body.reason], [true, ""]);
  r = await call(db, "POST", "signup", { username: "Ana", key: KEY_A, device: "phone" });
  assert.equal(r.status, 201);
  assert.equal(r.body.username, "Ana");
  assert.ok(r.body.token.length >= 40);
  r = await call(db, "GET", "username/ana");
  assert.equal(r.body.available, false);
  assert.match(r.body.reason, /taken/);
  r = await call(db, "POST", "signup", { username: "ANA", key: KEY_B });
  assert.equal(r.status, 409);
  assert.equal(r.body.field, "username");
  assert.match(r.body.error, /taken\. Pick another/);
});

test("bad sign-ups are refused", async () => {
  const db = freshDb();
  let r = await call(db, "POST", "signup", { username: "root", key: KEY_A });
  assert.equal(r.status, 400);
  r = await call(db, "POST", "signup", { username: "bob", key: "password123" });
  assert.equal(r.status, 400);
  assert.match(r.body.error, /Update the app/);
  r = await call(db, "POST", "signup", { username: "bob", key: KEY_A.toUpperCase() });
  assert.equal(r.status, 400);
  const raw = await handle(new Request(BASE + "signup", { method: "POST", body: "{nope" }),
    db, "signup");
  assert.equal(raw.status, 400);
});

test("the database holds no password and no token", async () => {
  const db = freshDb();
  const r = await call(db, "POST", "signup", { username: "cleo", key: KEY_A });
  const user = db.db.prepare("SELECT * FROM pycmd_users").get();
  assert.notEqual(user.hash, KEY_A);
  assert.equal(user.hash.length, 64);
  assert.equal(user.salt.length, 32);
  const session = db.db.prepare("SELECT * FROM pycmd_sessions").get();
  assert.notEqual(session.token_hash, r.body.token);
  assert.ok(!JSON.stringify(user).includes(KEY_A));
  // The same key twice gives different stored hashes: salts are random.
  await call(db, "POST", "signup", { username: "dev", key: KEY_A });
  const hashes = db.db.prepare("SELECT hash FROM pycmd_users").all().map((u) => u.hash);
  assert.notEqual(hashes[0], hashes[1]);
});

test("log in, wrong password, unknown user say the same thing", async () => {
  const db = freshDb();
  await call(db, "POST", "signup", { username: "eli", key: KEY_A });
  let r = await call(db, "POST", "login", { username: "ELI", key: KEY_A, device: "pc" });
  assert.equal(r.status, 200);
  assert.equal(r.body.username, "eli");
  const wrong = await call(db, "POST", "login", { username: "eli", key: KEY_B });
  const nobody = await call(db, "POST", "login", { username: "nobody", key: KEY_B });
  assert.equal(wrong.status, 401);
  assert.equal(nobody.status, 401);
  assert.equal(wrong.body.error, nobody.body.error);
});

test("too many wrong passwords are slowed down", async () => {
  const db = freshDb();
  await call(db, "POST", "signup", { username: "fay", key: KEY_A });
  for (let i = 0; i < 10; i++) {
    const r = await call(db, "POST", "login", { username: "fay", key: KEY_B },
      { ip: `9.9.9.${i}` });
    assert.equal(r.status, 401);
  }
  // Even the right password waits now: guessing has to stop, for everyone.
  const r = await call(db, "POST", "login", { username: "fay", key: KEY_A }, { ip: "8.8.8.8" });
  assert.equal(r.status, 429);
});

test("sign-ups from one address are limited", async () => {
  const db = freshDb();
  for (let i = 0; i < 8; i++) {
    const r = await call(db, "POST", "signup", { username: `user${i}`, key: KEY_A },
      { ip: "5.5.5.5" });
    assert.equal(r.status, 201);
  }
  const r = await call(db, "POST", "signup", { username: "user9", key: KEY_A }, { ip: "5.5.5.5" });
  assert.equal(r.status, 429);
  const other = await call(db, "POST", "signup", { username: "user9", key: KEY_A },
    { ip: "6.6.6.6" });
  assert.equal(other.status, 201);
});

test("signed-in calls need a real token", async () => {
  const db = freshDb();
  let r = await call(db, "GET", "me");
  assert.equal(r.status, 401);
  assert.equal(r.body.signed_out, true);
  r = await call(db, "GET", "me", undefined, { token: "x".repeat(43) });
  assert.equal(r.status, 401);
  r = await call(db, "GET", "nothing-here");
  assert.equal(r.status, 404);
  r = await call(db, "GET", "username/100%");
  assert.equal(r.status, 200);
  assert.equal(r.body.available, false);
});

test("progress: save, read, and a second device that is behind", async () => {
  const db = freshDb();
  const phone = (await call(db, "POST", "signup", { username: "gus", key: KEY_A })).body.token;
  const pc = (await call(db, "POST", "login", { username: "gus", key: KEY_A })).body.token;
  let r = await call(db, "GET", "progress", undefined, { token: phone });
  assert.deepEqual([r.body.version, r.body.data], [0, null]);
  r = await call(db, "PUT", "progress", { data: { xp: 10 }, base_version: 0, device: "phone" },
    { token: phone });
  assert.deepEqual([r.status, r.body.version], [200, 1]);
  // The PC read nothing yet and tries to create: it is told about version 1.
  r = await call(db, "PUT", "progress", { data: { xp: 20 }, base_version: 0 }, { token: pc });
  assert.equal(r.status, 409);
  assert.deepEqual([r.body.version, r.body.data], [1, { xp: 10 }]);
  r = await call(db, "PUT", "progress", { data: { xp: 30 }, base_version: 1, device: "pc" },
    { token: pc });
  assert.deepEqual([r.status, r.body.version], [200, 2]);
  r = await call(db, "GET", "progress", undefined, { token: phone });
  assert.deepEqual([r.body.version, r.body.data, r.body.device], [2, { xp: 30 }, "pc"]);
  r = await call(db, "GET", "me", undefined, { token: phone });
  assert.equal(r.body.progress.version, 2);
  assert.equal(r.body.sessions, 2);
});

test("progress must be an object, and not a huge one", async () => {
  const db = freshDb();
  const t = (await call(db, "POST", "signup", { username: "hana", key: KEY_A })).body.token;
  let r = await call(db, "PUT", "progress", { data: [1, 2], base_version: 0 }, { token: t });
  assert.equal(r.status, 400);
  r = await call(db, "PUT", "progress", { data: { big: "x".repeat(350 * 1024) }, base_version: 0 },
    { token: t });
  assert.equal(r.status, 413);
});

test("log out ends that session only", async () => {
  const db = freshDb();
  const a = (await call(db, "POST", "signup", { username: "ivo", key: KEY_A })).body.token;
  const b = (await call(db, "POST", "login", { username: "ivo", key: KEY_A })).body.token;
  let r = await call(db, "POST", "logout", {}, { token: a });
  assert.equal(r.status, 200);
  r = await call(db, "GET", "me", undefined, { token: a });
  assert.equal(r.status, 401);
  r = await call(db, "GET", "me", undefined, { token: b });
  assert.equal(r.status, 200);
});

test("changing the password signs other devices out", async () => {
  const db = freshDb();
  const a = (await call(db, "POST", "signup", { username: "jun", key: KEY_A })).body.token;
  const b = (await call(db, "POST", "login", { username: "jun", key: KEY_A })).body.token;
  let r = await call(db, "POST", "password", { old_key: KEY_B, new_key: KEY_B }, { token: a });
  assert.equal(r.status, 401);
  r = await call(db, "POST", "password", { old_key: KEY_A, new_key: KEY_B }, { token: a });
  assert.equal(r.status, 200);
  assert.equal((await call(db, "GET", "me", undefined, { token: a })).status, 200);
  assert.equal((await call(db, "GET", "me", undefined, { token: b })).status, 401);
  assert.equal((await call(db, "POST", "login", { username: "jun", key: KEY_A })).status, 401);
  assert.equal((await call(db, "POST", "login", { username: "jun", key: KEY_B })).status, 200);
});

test("deleting the account removes everything, and frees the name", async () => {
  const db = freshDb();
  const t = (await call(db, "POST", "signup", { username: "kai", key: KEY_A })).body.token;
  await call(db, "PUT", "progress", { data: { xp: 1 }, base_version: 0 }, { token: t });
  let r = await call(db, "POST", "account/delete", { key: KEY_B }, { token: t });
  assert.equal(r.status, 401);
  r = await call(db, "POST", "account/delete", { key: KEY_A }, { token: t });
  assert.equal(r.status, 200);
  for (const table of ["pycmd_users", "pycmd_sessions", "pycmd_progress"]) {
    assert.equal(db.db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get().n, 0, table);
  }
  r = await call(db, "GET", "username/kai");
  assert.equal(r.body.available, true);
});

test("an expired session is refused", async () => {
  const db = freshDb();
  const t = (await call(db, "POST", "signup", { username: "lea", key: KEY_A })).body.token;
  db.db.prepare("UPDATE pycmd_sessions SET expires_at = 1").run();
  assert.equal((await call(db, "GET", "me", undefined, { token: t })).status, 401);
});

test("the tables are made on first use, and making them twice is harmless", async () => {
  const db = freshDb();
  await call(db, "GET", "username/someone");
  _resetForTests();
  const r = await call(db, "GET", "username/someone");
  assert.equal(r.status, 200);
});

test("progress is stored compressed, and read back the same", async () => {
  const db = freshDb();
  const t = (await call(db, "POST", "signup", { username: "mia", key: KEY_A })).body.token;
  const ids = Array.from({ length: 1800 }, (_, i) => `${i % 60}.${i % 30}.predict`);
  const data = { done: { python: ids, go: ids }, xp: 36000 };
  await call(db, "PUT", "progress", { data, base_version: 0 }, { token: t });
  const stored = db.db.prepare("SELECT data FROM pycmd_progress").get().data;
  assert.ok(stored.startsWith("gz:"));
  assert.ok(stored.length * 5 < JSON.stringify(data).length, `${stored.length} stored`);
  const r = await call(db, "GET", "progress", undefined, { token: t });
  assert.deepEqual(r.body.data, data);
  // A row written by the previous version, uncompressed, still reads.
  db.db.prepare("UPDATE pycmd_progress SET data = ?").run(JSON.stringify({ xp: 5 }));
  assert.deepEqual((await call(db, "GET", "progress", undefined, { token: t })).body.data, { xp: 5 });
});

test("cloud storage: 800 KB each, files in and out, quota enforced", async () => {
  const db = freshDb();
  const t = (await call(db, "POST", "signup", { username: "noa", key: KEY_A })).body.token;
  const put = (path, bytes) => call(db, "PUT", "files/" + encodeURIComponent(path),
    { content_b64: Buffer.from(bytes).toString("base64") }, { token: t });
  let r = await put("notes/hello.py", "print('hi')\n");
  assert.equal(r.status, 200);
  assert.equal(r.body.size, 12);
  r = await call(db, "GET", "files", undefined, { token: t });
  assert.deepEqual([r.body.files.length, r.body.used, r.body.quota], [1, 12, 800 * 1024]);
  r = await call(db, "GET", "files/" + encodeURIComponent("notes/hello.py"), undefined, { token: t });
  assert.equal(Buffer.from(r.body.content_b64, "base64").toString(), "print('hi')\n");
  r = await put("big.bin", new Uint8Array(800 * 1024));
  assert.equal(r.status, 413);
  assert.match(r.body.error, /does not fit/);
  r = await put("fits.bin", new Uint8Array(800 * 1024 - 12));
  assert.equal(r.status, 200);
  r = await put("notes/hello.py", "x");  // replacing frees the old size first
  assert.equal(r.status, 200);
  assert.equal((await put("../escape", "x")).status, 400);
  assert.equal((await put("/abs", "x")).status, 400);
  assert.equal((await call(db, "GET", "files")).status, 401);
  r = await call(db, "DELETE", "files/fits.bin", undefined, { token: t });
  assert.equal(r.body.used, 1);
  assert.equal((await call(db, "DELETE", "files/fits.bin", undefined, { token: t })).status, 404);
  r = await call(db, "GET", "me", undefined, { token: t });
  assert.deepEqual(r.body.storage, { used: 1, quota: 800 * 1024 });
  await call(db, "POST", "account/delete", { key: KEY_A }, { token: t });
  assert.equal(db.db.prepare("SELECT COUNT(*) AS n FROM pycmd_files").get().n, 0);
});
