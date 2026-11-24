"""The human surface, in a browser: a web review console for held judgments.

The terminal console (review.py) works, but a reviewer should not need
a shell. This module serves the same queue as a small local web page:

    witness-gate-review-web --ledger gate-ledger.jsonl --port 8766

Open http://127.0.0.1:8766 and the page lists every undecided hold
(flagged, contested, blocked) with its verdict, its action, and the
witnesses' note and dissent. Approve, reject, or acknowledge from the
browser. Decisions are recorded through review.decide, so the rules
are identical to the terminal console: decisions are appended to the
decisions ledger beside the judgment ledger, hash-chained, and a
blocked judgment can be acknowledged but never approved.

The judgment ledger itself is never edited, and the server refuses to
serve a ledger whose hash chain does not verify.

This is a local operations tool. It binds to 127.0.0.1 by default and
has no authentication of its own: run it on the machine that holds the
ledger, or behind your own authenticated proxy. Widen --host only on
a network you control.

Standard library only, like the rest of the package.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .plug import verify_ledger
from .review import decide, holds

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Witness Gate · Review Console</title>
<style>
  body { margin:0; background:#050b18; color:#eef3fb;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { padding:18px 22px 6px; }
  h1 { margin:0; font-size:20px; letter-spacing:.04em; }
  header p { color:#a9bede; font-size:13px; margin:4px 0 0; }
  main { padding:12px 22px 30px; max-width:860px; }
  .card { background:rgba(8,16,34,.9); border:1px solid rgba(150,175,220,.35);
    border-radius:12px; padding:14px 16px; margin:12px 0; }
  .verdict { font-weight:700; letter-spacing:.06em; }
  .flagged { color:#f5b83d; } .contested { color:#f5b83d; }
  .blocked { color:#ef4444; } .clear { color:#35d07f; }
  .action { font-size:15px; margin:6px 0; }
  .meta { color:#a9bede; font-size:12.5px; line-height:1.5; }
  .row { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; align-items:center; }
  input { background:#0d1830; border:1px solid rgba(150,175,220,.4); color:#eef3fb;
    border-radius:8px; padding:8px 10px; font-size:13px; }
  button { appearance:none; border:1px solid rgba(150,175,220,.5);
    background:rgba(18,38,74,.9); color:#eef3fb; font-size:13px; font-weight:600;
    padding:8px 13px; border-radius:999px; cursor:pointer; }
  button:hover { background:rgba(30,58,110,.95); }
  button:disabled { opacity:.4; cursor:default; }
  #status { color:#a9bede; font-size:13px; padding:0 22px; }
</style>
</head>
<body>
<header>
  <h1>WITNESS GATE · REVIEW CONSOLE</h1>
  <p>Held judgments awaiting a human decision. Decisions are sealed into the
  decisions ledger. A blocked judgment can be acknowledged, never approved.</p>
</header>
<div id="status">loading…</div>
<main id="list"></main>
<script>
async function load(){
  const status = document.getElementById('status');
  const list = document.getElementById('list');
  const r = await fetch('/api/holds');
  const data = await r.json();
  if (!r.ok) { status.textContent = data.error || 'failed to load'; list.innerHTML=''; return; }
  status.textContent = data.holds.length
    ? data.holds.length + ' undecided hold(s). Chain verified.'
    : 'No undecided holds. Chain verified.';
  list.innerHTML = '';
  for (const h of data.holds) {
    const card = document.createElement('div'); card.className = 'card';
    const v = h.result.verdict;
    const vdiv = document.createElement('div');
    vdiv.className = 'verdict ' + v;
    vdiv.textContent = v.toUpperCase();
    card.appendChild(vdiv);
    const adiv = document.createElement('div');
    adiv.className = 'action';
    adiv.textContent = h.action;
    card.appendChild(adiv);
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = 'entry ' + h.hash.slice(0,12) + ' · operator ' +
      (h.operator || '');
    if (h.result.note) {
      meta.appendChild(document.createElement('br'));
      meta.appendChild(document.createTextNode(h.result.note));
    }
    card.appendChild(meta);
    const row = document.createElement('div'); row.className = 'row';
    const by = document.createElement('input');
    by.placeholder = 'your name'; by.size = 14;
    row.appendChild(by);
    for (const d of ['approved','rejected','acknowledged']) {
      if (v === 'blocked' && d === 'approved') continue;
      const b = document.createElement('button');
      b.textContent = d;
      b.addEventListener('click', async () => {
        if (!by.value.trim()) { by.focus(); return; }
        const resp = await fetch('/api/decide', { method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ entry: h.hash, decision: d, by: by.value.trim() }) });
        const out = await resp.json();
        if (!resp.ok) { status.textContent = out.error || 'decision failed'; return; }
        load();
      });
      row.appendChild(b);
    }
    card.appendChild(row);
    list.appendChild(card);
  }
}
load();
</script>
</body>
</html>
"""


def make_handler(ledger_path: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # keep stdout clean
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict):
            self._send(code, json.dumps(payload).encode(), "application/json")

        def do_GET(self):
            if self.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                return
            if self.path == "/api/holds":
                if not verify_ledger(ledger_path):
                    self._json(500, {"error": "ledger does not verify: "
                                      "the hash chain is broken"})
                    return
                self._json(200, {"holds": holds(ledger_path)})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/decide":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length) or b"{}")
                body = decide(ledger_path, payload["entry"],
                              payload["decision"], payload["by"])
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"recorded": body})

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(prog="witness-gate-review-web")
    parser.add_argument("--ledger", required=True,
                        help="path to the sealed judgment ledger (JSONL)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    if not verify_ledger(args.ledger):
        print("ledger does not verify: the hash chain is broken")
        return 1
    server = ThreadingHTTPServer((args.host, args.port),
                                 make_handler(args.ledger))
    print(f"review console: http://{args.host}:{args.port} "
          f"(ledger {args.ledger})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
