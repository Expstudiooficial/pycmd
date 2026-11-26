#!/usr/bin/env python3
"""Writes website/PROMPT-FOR-WEBSITE-CLAUDE.md: everything the assistant that
maintains pycmd.pages.dev needs to add the accounts API, with the code inline
(so it does not need access to this repository) and taken from the files
that tools/test_account.py and website/test/ actually test.

    python3 tools/make_website_prompt.py
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "website")


def read(*parts):
    with open(os.path.join(WEB, *parts), encoding="utf-8") as handle:
        return handle.read().rstrip("\n")


PROMPT = """# Add PyCmd accounts to pycmd.pages.dev

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
{route}
```

### `lib/pycmd-api.js`

```js
{api}
```

## Rules - please do not change these

The apps are already built against this exact API, so:

- Keep the URLs (`/api/v1/...`), the JSON field names, the status codes and
  the binding name `pycmddata1`.
- Do not change the password key scheme. The apps send `key` = PBKDF2-SHA256
  of the password (NFC), salt `"pycmd-account-v1:" + username.toLowerCase()`,
  600,000 rounds, 32 bytes, lower-case hex. Test vector: username `Tester`,
  password `correct horse staple` →
  `{vector}`.
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
async function pycmdKey(username, password) {{
  const text = new TextEncoder();
  const material = await crypto.subtle.importKey(
    "raw", text.encode(password.normalize("NFC")), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    {{ name: "PBKDF2", hash: "SHA-256", iterations: 600000,
      salt: text.encode("pycmd-account-v1:" + username.trim().toLowerCase()) }},
    material, 256);
  return [...new Uint8Array(bits)].map((b) => b.toString(16).padStart(2, "0")).join("");
}}
```

Keep the token it gets back in `sessionStorage` (not `localStorage`), and send
it as `Authorization: Bearer <token>`.

## Check it after deploying

1. `https://pycmd.pages.dev/api/v1/health` should return
   `{{"ok":true,"service":"pycmd","api":1,"database":true}}`.
   - `503` with "not connected" means the binding is missing or the site was
     not redeployed after adding it.
   - `404` means the `functions/` folder is not at the project root (or the
     project uses `_worker.js` - see above).
2. `https://pycmd.pages.dev/api/v1/username/someone` should return
   `{{"ok":true,"available":true,"reason":""}}`.
3. `https://pycmd.pages.dev/api/v1/username/admin` should say it is reserved.
4. A sign-up and sign-in round trip, with the test vector as the key:

```sh
curl -s -X POST https://pycmd.pages.dev/api/v1/signup \\
  -H 'content-type: application/json' \\
  -d '{{"username":"pycmd-check","key":"{vector}","device":"curl"}}'
# -> {{"ok":true,"username":"pycmd-check","token":"..."}}

curl -s -X POST https://pycmd.pages.dev/api/v1/login \\
  -H 'content-type: application/json' \\
  -d '{{"username":"pycmd-check","key":"{vector}","device":"curl"}}'
# -> {{"ok":true,...}}  (a different key -> 401 "Wrong username or password.")

# Then delete the test account again (use the token from the login):
curl -s -X POST https://pycmd.pages.dev/api/v1/account/delete \\
  -H 'content-type: application/json' -H 'authorization: Bearer <token>' \\
  -d '{{"key":"{vector}"}}'
# -> {{"ok":true}}
```

5. The rest of the site still looks and works exactly as before, and the
   "disband" sponsor is gone.

When you are done, tell me what `/api/v1/health` returns, and anything you had
to do differently from the steps above.

## The tables (for reference only - the API creates them)

```sql
{schema}
```
"""


def main():
    vector = "423ab8b3a7d9d795774e1b8986a53c2ecc9f3cf41f73899a09d46571da0076d8"
    text = PROMPT.format(route=read("functions", "api", "v1", "[[path]].js"),
                         api=read("lib", "pycmd-api.js"), vector=vector,
                         schema=read("schema.sql"))
    path = os.path.join(WEB, "PROMPT-FOR-WEBSITE-CLAUDE.md")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {path} ({len(text):,} characters)")


if __name__ == "__main__":
    main()
