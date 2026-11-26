# PyCmd accounts on pycmd.pages.dev

What the website needs so that PyCmd for Android (2.9.0+) and PyCmd for
Windows (4.5+) can sign people in and keep their Learn progress in step.
The apps hold no database credential: they call this API over HTTPS, and only
the API, running on Cloudflare next to the database, touches the database.

```
PyCmd app  ──HTTPS──▶  pycmd.pages.dev/api/v1/…  ──binding──▶  D1 "pycmddata1"
(Android, Windows)     (Pages Function, this folder)            (500 MB, free)
```

## Files

| Path | What it is |
| --- | --- |
| `lib/pycmd-api.js` | The whole API: routing, sign-up, sign-in, sessions, progress, rate limits. |
| `functions/api/v1/[[path]].js` | The Pages Function that hands every `/api/v1/*` request to it. |
| `schema.sql` | The tables, for reference. The API creates them itself on first use. |
| `test/` | Tests: `node --test website/test/api.test.mjs`, and a local server for the apps. |
| `PROMPT-FOR-WEBSITE-CLAUDE.md` | Instructions for whoever maintains the site. |

Both `lib/` and `functions/` go at the **root of the Pages project** (next to
`package.json`, not inside the build output folder). The D1 database is bound
to the Pages project under **Settings → Bindings** as variable name
`pycmddata1`, database `pycmddata1`; a binding takes effect on the next deploy.

## The API

Every reply is JSON with `ok: true|false`, and on failure an `error` sentence
the apps show as it is. Signed-in calls send `Authorization: Bearer <token>`.

| Call | Body | Reply |
| --- | --- | --- |
| `GET /api/v1/health` | | `{ok, service, api, database}` |
| `GET /api/v1/username/<name>` | | `{ok, available, reason}` |
| `POST /api/v1/signup` | `{username, key, device}` | `201 {ok, username, token}` · `409` taken · `429` too many |
| `POST /api/v1/login` | `{username, key, device}` | `{ok, username, token}` · `401` · `429` |
| `POST /api/v1/logout` | | `{ok}` |
| `GET /api/v1/me` | | `{ok, username, created_at, progress, sessions}` |
| `GET /api/v1/progress` | | `{ok, version, data, updated_at, device}` |
| `PUT /api/v1/progress` | `{data, base_version, device}` | `{ok, version}` · `409 {conflict, version, data}` |
| `POST /api/v1/password` | `{old_key, new_key}` | `{ok}`, and every other session ends |
| `POST /api/v1/account/delete` | `{key}` | `{ok}`, and everything of the account is gone |

**Usernames**: 3–24 characters of `A-Z a-z 0-9 _ . -`, starting and ending with
a letter or digit, unique ignoring case (`Ana` and `ana` are the same name).
A few names are reserved (`admin`, `pycmd`, `support`, …).

**Passwords never reach the server.** The app sends `key` instead:

```
key = hex( PBKDF2-HMAC-SHA256(
        password  = UTF-8 of the password, NFC-normalised,
        salt      = UTF-8 of "pycmd-account-v1:" + username.toLowerCase(),
        rounds    = 600000,
        length    = 32 bytes ) )            → 64 lower-case hex digits
```

Test vector: username `Tester`, password `correct horse staple` →
`423ab8b3a7d9d795774e1b8986a53c2ecc9f3cf41f73899a09d46571da0076d8`.

The server stretches `key` again (PBKDF2, random 16-byte salt per user) and
stores only that. Session tokens are 32 random bytes; only their SHA-256 is
stored. Failed sign-ins are limited per username (10 per 15 minutes) and per
address (40 per 15 minutes), sign-ups to 8 an hour per address; addresses are
kept only as salted hashes, and only for a day.

**Progress** is the app's Learn progress file as JSON (at most 300 KB). Saving
needs the version the device last read (`base_version`); if another device
saved since, the reply is `409` with the newer copy, and the app merges and
saves again - nobody's lessons are overwritten.

## Testing

```
node --test website/test/api.test.mjs            # the API, on SQLite
python3 tools/test_account.py                     # the apps' client against it
node website/test/serve-local.mjs 8787            # a local API for trying the apps
PYCMD_CLOUD_URL=http://127.0.0.1:8787/api/v1 …    # point an app build at it
```

After deploying: `curl https://pycmd.pages.dev/api/v1/health` should say
`"database":true`.
