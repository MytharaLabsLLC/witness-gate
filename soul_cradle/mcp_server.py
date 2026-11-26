"""The Witness Gate as an MCP tool: agent frameworks call it directly.

Model Context Protocol servers expose tools that agent frameworks
(LangGraph, CrewAI, the OpenAI Agents SDK, Claude, and others) can
invoke. This module is a zero-dependency MCP server over stdio that
exposes four tools:

    witness_gate_assess(action, evidence) -> panel verdict
    witness_gate_verify_ledger(ledger?) -> does the sealed record verify
    witness_gate_review_queue(ledger?) -> judgments awaiting a human
    witness_gate_rubrics() -> every assessor rubric and version

The framework's agent calls the tool before carrying out a
consequential action; the panel's verdict comes back as the tool
result, and every judgment is sealed in the ledger when one is
configured.

Run it:

    python -m soul_cradle.mcp_server --ledger gate-ledger.jsonl

Point your framework's MCP configuration at that command. The server
speaks newline-delimited JSON-RPC on stdin/stdout and nothing else;
diagnostics never touch stdout.

Standard library only, like the rest of the package.
"""

from __future__ import annotations

import argparse
import json
import sys

from .assessors import rubric_inventory
from .plug import Gate, verify_ledger
from .review import holds

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "witness-gate", "version": "0.2.0"}

TOOL = {
    "name": "witness_gate_assess",
    "description": (
        "Put a proposed agent action before the eight Witness Gate "
        "assessors BEFORE carrying it out. Returns the panel verdict: "
        "clear (proceed), flagged (hold for a human), contested (the "
        "witnesses disagree; a human decides, dissent preserved), or "
        "blocked (a critical finding; refuse the action, no override). "
        "Evidence is a dict of observable facts about the action; the "
        "core keys are principal_consent, fully_disclosed, reversible, "
        "and deception_involved. For every assessor the evidence "
        "engages, missing evidence fails closed; a packet that "
        "engages no assessor is cleared by universal abstention."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "description": "What the agent proposes to do."},
            "evidence": {"type": "object",
                         "description": "Observable facts about the action."},
        },
        "required": ["action"],
    },
}

_LEDGER_PROP = {
    "ledger": {"type": "string",
               "description": "Path to the judgment ledger (JSONL). "
                              "Defaults to the server's configured ledger."},
}

TOOLS = [
    TOOL,
    {
        "name": "witness_gate_verify_ledger",
        "description": (
            "Verify the hash chain of a sealed Witness Gate judgment "
            "ledger. Returns ok: true when every entry's hash chains to "
            "the one before it, false when the record has been altered."
        ),
        "inputSchema": {"type": "object", "properties": _LEDGER_PROP},
    },
    {
        "name": "witness_gate_review_queue",
        "description": (
            "List the judgments a human still needs to decide: entries "
            "whose verdict was flagged, contested, or blocked and that "
            "have no recorded human decision yet. Read-only; recording "
            "a decision is a human act in the review console."
        ),
        "inputSchema": {"type": "object", "properties": _LEDGER_PROP},
    },
    {
        "name": "witness_gate_rubrics",
        "description": (
            "Return every assessor's rubric: name, domain question, "
            "version, effective date, source, and check count. For "
            "audits and for explaining what the panel judges against."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class McpServer:
    def __init__(self, gate: Gate, ledger_path: str | None = None):
        self.gate = gate
        self.ledger_path = ledger_path if ledger_path is not None \
            else gate.ledger_path

    def handle(self, msg: dict) -> dict | None:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        if method == "initialize":
            return self._reply(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            })
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        if method == "ping":
            return self._reply(msg_id, {})
        if method == "tools/list":
            return self._reply(msg_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._reply(msg_id, self._call(msg.get("params") or {}))
        if msg_id is not None:
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
        return None

    def _ledger_for(self, args: dict) -> str | None:
        return args.get("ledger") or self.ledger_path

    @staticmethod
    def _payload(payload) -> dict:
        return {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "structuredContent": payload,
            "isError": False,
        }

    @staticmethod
    def _error(text: str) -> dict:
        return {"content": [{"type": "text", "text": text}], "isError": True}

    def _call(self, params: dict) -> dict:
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "witness_gate_assess":
            action = args.get("action")
            evidence = args.get("evidence") or {}
            if not isinstance(action, str) or not isinstance(evidence, dict):
                return self._error(
                    "action must be a string, evidence an object")
            return self._payload(self.gate.check(action, evidence).to_dict())
        if name == "witness_gate_rubrics":
            return self._payload(rubric_inventory())
        if name in ("witness_gate_verify_ledger", "witness_gate_review_queue"):
            ledger = self._ledger_for(args)
            if not ledger:
                return self._error(
                    "no ledger configured: start the server with --ledger "
                    "or pass a ledger path in the call")
            try:
                if name == "witness_gate_verify_ledger":
                    return self._payload(
                        {"ledger": ledger, "ok": verify_ledger(ledger)})
                queue = [{"hash": e.get("hash"),
                          "action": e.get("action"),
                          "verdict": e.get("result", {}).get("verdict")}
                         for e in holds(ledger)]
                return self._payload({"ledger": ledger, "holds": queue})
            except (OSError, ValueError) as exc:
                return self._error(str(exc))
        return self._error(f"unknown tool: {name}")

    @staticmethod
    def _reply(msg_id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mcp_server")
    parser.add_argument("--ledger", default=None,
                        help="path to the sealed judgment ledger (JSONL)")
    parser.add_argument("--operator", default="mcp-server")
    args = parser.parse_args(argv)
    server = McpServer(Gate(operator=args.operator, ledger_path=args.ledger),
                       ledger_path=args.ledger)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = server.handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
