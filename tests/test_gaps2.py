"""Tests for the gap fixes: web review console, expanded MCP tools,
and the framework adapters."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from soul_cradle.adapters import (crewai_tool, langgraph_node,
                                  openai_function_tool)
from soul_cradle.mcp_server import McpServer
from soul_cradle.plug import Gate, GateBlocked
from soul_cradle.review import holds
from soul_cradle.review_web import make_handler

CLEAR = {"principal_consent": True, "fully_disclosed": True,
         "reversible": True, "deception_involved": False,
         "disproportionate_harm": False, "hidden_costs_addressed": True,
         "sustains_long_term": True, "safe_on_repetition": True,
         "strengthens_relationship": True, "variance": "low",
         "actor": "agent-1", "action_type": "refund",
         "affected_parties": ["customer"], "precedent_setting": False,
         "contradicts_commitments": False}


@pytest.fixture()
def ledger(tmp_path):
    path = str(tmp_path / "gate.jsonl")
    gate = Gate(operator="test", ledger_path=path)
    gate.check("refund with consent on file", CLEAR)          # clear
    gate.check("refund, consent unclear", {"principal_consent": True})
    gate.check("deceptive charge", {"deception_involved": True})
    return path


def test_review_queue_contents(ledger):
    queue = holds(ledger)
    verdicts = sorted(e["result"]["verdict"] for e in queue)
    assert verdicts == ["blocked", "flagged"]


def _serve(ledger):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ledger))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _get(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, resp.read().decode()


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_web_console_flow(ledger):
    server, base = _serve(ledger)
    try:
        status, page = _get(base + "/")
        assert status == 200 and "REVIEW CONSOLE" in page
        status, body = _get(base + "/api/holds")
        data = json.loads(body)
        assert status == 200 and len(data["holds"]) == 2
        flagged = next(e for e in data["holds"]
                       if e["result"]["verdict"] == "flagged")
        blocked = next(e for e in data["holds"]
                       if e["result"]["verdict"] == "blocked")
        status, out = _post(base + "/api/decide",
                            {"entry": blocked["hash"],
                             "decision": "approved", "by": "dana"})
        assert status == 400  # a block can never be approved
        status, out = _post(base + "/api/decide",
                            {"entry": flagged["hash"],
                             "decision": "approved", "by": "dana"})
        assert status == 200 and out["recorded"]["decision"] == "approved"
        assert len(holds(ledger)) == 1
    finally:
        server.shutdown()


def test_mcp_tools(ledger):
    gate = Gate(operator="test", ledger_path=ledger)
    server = McpServer(gate, ledger_path=ledger)

    def call(name, args=None, mid=1):
        reply = server.handle({"jsonrpc": "2.0", "id": mid,
                               "method": "tools/call",
                               "params": {"name": name,
                                          "arguments": args or {}}})
        return reply["result"]

    listing = server.handle({"jsonrpc": "2.0", "id": 0,
                             "method": "tools/list"})
    names = [t["name"] for t in listing["result"]["tools"]]
    assert names == ["witness_gate_assess", "witness_gate_verify_ledger",
                     "witness_gate_review_queue", "witness_gate_rubrics"]

    rubrics = call("witness_gate_rubrics")["structuredContent"]
    assert len(rubrics) == 8 and "demeter" in rubrics

    verified = call("witness_gate_verify_ledger")["structuredContent"]
    assert verified["ok"] is True

    queue = call("witness_gate_review_queue")["structuredContent"]
    assert sorted(h["verdict"] for h in queue["holds"]) == ["blocked",
                                                            "flagged"]

    verdict = call("witness_gate_assess",
                   {"action": "refund", "evidence": CLEAR})
    assert verdict["structuredContent"]["verdict"] == "clear"
    assert call("nope")["isError"] is True


def test_adapters(tmp_path):
    gate = Gate(operator="test",
                ledger_path=str(tmp_path / "gate.jsonl"))

    node = langgraph_node(gate)
    out = node({"action": "refund", "evidence": CLEAR})
    assert out["verdict"] == "clear" and out["held"] is False
    out = node({"action": "refund", "evidence": {"principal_consent": True}})
    assert out["held"] is True
    with pytest.raises(GateBlocked):
        node({"action": "deceptive charge",
              "evidence": {"deception_involved": True}})

    tool = crewai_tool(gate)
    payload = json.loads(tool("refund", json.dumps(CLEAR)))
    assert payload["verdict"] == "clear"
    assert tool.__name__ == "witness_gate"

    definition, handler = openai_function_tool(gate)
    assert definition["type"] == "function"
    assert definition["function"]["name"] == "witness_gate_assess"
    payload = json.loads(handler({"action": "refund", "evidence": CLEAR}))
    assert payload["verdict"] == "clear"
    payload = json.loads(handler({"evidence": CLEAR}))
    assert "error" in payload


def test_review_web_never_injects_ledger_text_as_html():
    """F5 regression: operator and note come from the ledger, so the
    console page must insert them as text, never as markup."""
    from soul_cradle.review_web import PAGE
    assert "createTextNode" in PAGE
    assert "meta.textContent" in PAGE
    assert "'<br>' + h.result.note" not in PAGE
    assert "(h.operator || '') +" not in PAGE
