// The accounts API on http://127.0.0.1:<port>/api/v1/, backed by SQLite, for
// testing the apps against it without Cloudflare. Prints the port, then serves
// until killed.
//
//   node website/test/serve-local.mjs [port]
import http from "node:http";
import { D1 } from "./d1-shim.mjs";
import { handle } from "../lib/pycmd-api.js";

const db = new D1();
const server = http.createServer(async (req, res) => {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = Buffer.concat(chunks);
  const url = new URL(req.url, "http://127.0.0.1");
  if (!url.pathname.startsWith("/api/v1/")) {
    res.writeHead(404).end();
    return;
  }
  const headers = { ...req.headers, "cf-connecting-ip": req.socket.remoteAddress };
  const request = new Request(url, {
    method: req.method, headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : body,
  });
  const response = await handle(request, db, url.pathname.slice("/api/v1/".length));
  res.writeHead(response.status, Object.fromEntries(response.headers));
  res.end(Buffer.from(await response.arrayBuffer()));
});
server.listen(Number(process.argv[2] || 0), "127.0.0.1", () => {
  console.log(server.address().port);
});
