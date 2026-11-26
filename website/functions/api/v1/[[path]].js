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
