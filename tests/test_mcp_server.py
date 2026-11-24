import json

from soul_cradle.mcp_server import McpServer
from soul_cradle.plug import Gate

GOOD = {"principal_consent": True, "fully_disclosed": True,
        "reversible": True, "deception_involved": False,
        "affected_parties": ["customer"], "disproportionate_harm": False,
        "contradicts_commitments": False, "sustains_long_term": True,
        "hidden_costs_addressed": True, "safe_on_repetition": True,
        "strengthens_relationship": True, "precedent_setting": False,
        "variance": "low", "actor": "agent-7", "action_type": "refund"}


def server():
    return McpServer(Gate(operator="test"))


def test_initialize_and_tools_list():
    s = server()
    reply = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {}})
    assert reply["result"]["serverInfo"]["name"] == "witness-gate"
    reply = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in reply["result"]["tools"]]
    assert names == ["witness_gate_assess", "witness_gate_verify_ledger",
                     "witness_gate_review_queue", "witness_gate_rubrics"]
    assert s.handle({"method": "notifications/initialized"}) is None


def test_tool_call_clear_and_blocked():
    s = server()
    reply = s.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": "witness_gate_assess",
                                 "arguments": {"action": "refund",
                                               "evidence": GOOD}}})
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["verdict"] == "clear"
    assert reply["result"]["isError"] is False
    bad = dict(GOOD, deception_involved=True)
    reply = s.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                      "params": {"name": "witness_gate_assess",
                                 "arguments": {"action": "deceive",
                                               "evidence": bad}}})
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["verdict"] == "blocked"


def test_unknown_method_errors():
    reply = server().handle({"jsonrpc": "2.0", "id": 9, "method": "nope"})
    assert reply["error"]["code"] == -32601
