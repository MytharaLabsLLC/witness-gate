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
    GET /policy   -> the policy pack this server applies, if any

Customer policy packs (see soul_cradle.policy) work here exactly as
they do in the Python API, in two ways. Start the server with
--policy pack.json and that pack judges every request. Or send one
pack as a JSON object in a single request's "policy" field and it
judges that request only, replacing any server pack for that call.
Policy findings carry "policy:<pack>:<rule>" check ids, the applied
pack's name, version, and sha256 are reported in the response's
"policy" field and sealed into the ledger entry, and an invalid pack
fails closed: a bad --policy file stops the server from starting, and
a bad per-request pack gets a 400 with nothing judged. A pack is
accepted only as a JSON object, never as a file path; the server does
not read files on a caller's say-so.

Run it inside your own environment:

    python -m soul_cradle.gate_server --port 8765 \
        --ledger gate-ledger.jsonl --policy customer-policy.json

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
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .assessors import rubric_inventory
from .plug import Gate
from .policy import PolicyError

SERVICE = "witness-gate"


def _scoped_gate(base: Gate, policy) -> Gate:
    """A gate identical to base but carrying the given policy pack.

    Construction validates the pack through load_policy, so a bad
    pack raises PolicyError here and no judgment is ever issued
    without the law that was asked for.
    """
    return Gate(
        operator=base.operator,
        ledger_path=base.ledger_path,
        on_hold=base.on_hold,
        default_evidence=base.default_evidence,
        actor=base.actor,
        policy=policy,
    )


def make_handler(gate: Gate):
    # One lock around gate resolution and judgment: a per-request
    # gate seals into the same ledger as the server gate, and the
    # hash chain only stays truthful if seals never interleave.
    lock = threading.Lock()
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
            elif self.path == "/policy":
                pack = gate.policy_pack
                self._send(200, {
                    "service": SERVICE,
                    "policy": pack.identity() if pack is not None else None,
                })
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
            with lock:
                judge = gate
                if "policy" in body:
                    pack = body["policy"]
                    if not isinstance(pack, dict):
                        self._send(400, {"error": "bad request: policy must "
                                                  "be a policy pack object"})
                        return
                    try:
                        judge = _scoped_gate(gate, pack)
                    except PolicyError as exc:
                        self._send(400, {"error": f"invalid policy pack: {exc}"})
                        return
                result = judge.check(action, evidence)
            payload = result.to_dict()
            payload["service"] = SERVICE
            pack = judge.policy_pack
            payload["policy"] = pack.identity() if pack is not None else None
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
    parser.add_argument("--policy", default=None,
                        help="path to a customer policy pack (JSON) "
                             "applied to every judgment")
    args = parser.parse_args(argv)
    try:
        gate = Gate(operator=args.operator, ledger_path=args.ledger,
                    policy=args.policy)
    except PolicyError as exc:
        # Fail closed: no law loaded, no server. A gate that cannot
        # load its pack must never come up judging bare.
        print(f"{SERVICE}: refusing to start: {exc}", file=sys.stderr)
        sys.exit(2)
    server = serve(args.host, args.port, gate)
    print(f"{SERVICE} listening on http://{args.host}:{args.port} "
          f"(POST /assess, GET /health, GET /rubrics, GET /policy)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
