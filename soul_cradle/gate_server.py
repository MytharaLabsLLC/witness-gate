"""The Witness Gate as a local HTTP service: callable from any stack.

The panel is Python. Agents are not all Python. This module serves the
gate over plain HTTP with a JSON contract, so any language, framework,
or tool that can make an HTTP request can put an action before the
witnesses:

    POST /assess
    {"action": "Send the weekly report",
     "evidence": {"principal_consent": true, "fully_disclosed": true,
                  "reversible": true, "deception_involved": false}}

    -> 200 {"verdict": "clear" | "flagged" | "contested" | "blocked",
            "note": "...", "dissent": [...], "judgments": [...]}

    GET /health   -> {"ok": true, "service": "witness-gate"}
    GET /rubrics  -> every assessor rubric, version, and source

Run it inside your own environment:

    python -m soul_cradle.gate_server --port 8765 \
        --ledger gate-ledger.jsonl

It binds to 127.0.0.1 by default. Widen --host only on a network you
control: whoever can reach this port can ask for judgments. Every
judgment is sealed in the ledger when one is configured. The service
judges and seals; enforcement stays with the caller, the same split as
the Python API: clear means run it, flagged or contested means a human
decides, blocked means refuse it, and no caller setting turns a block
into a pass.

Standard library only, like the rest of the package.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .assessors import rubric_inventory
from .plug import Gate

SERVICE = "witness-gate"


def make_handler(gate: Gate):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # keep stdout clean
            pass

        def _send(self, code: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"ok": True, "service": SERVICE})
            elif self.path == "/rubrics":
                self._send(200, {"rubrics": rubric_inventory()})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path not in ("/assess", "/check"):
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw.decode() or "{}")
                action = body["action"]
                evidence = body.get("evidence") or {}
                if not isinstance(action, str) or not isinstance(evidence, dict):
                    raise ValueError("action must be a string, evidence an object")
            except Exception as exc:
                self._send(400, {"error": f"bad request: {exc}"})
                return
            result = gate.check(action, evidence)
            payload = result.to_dict()
            payload["service"] = SERVICE
            self._send(200, payload)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765,
          gate: Optional[Gate] = None) -> ThreadingHTTPServer:
    gate = gate or Gate(operator="gate-server")
    return ThreadingHTTPServer((host, port), make_handler(gate))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gate_server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ledger", default=None,
                        help="path to the sealed judgment ledger (JSONL)")
    parser.add_argument("--operator", default="gate-server")
    args = parser.parse_args(argv)
    gate = Gate(operator=args.operator, ledger_path=args.ledger)
    server = serve(args.host, args.port, gate)
    print(f"{SERVICE} listening on http://{args.host}:{args.port} "
          f"(POST /assess, GET /health, GET /rubrics)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
