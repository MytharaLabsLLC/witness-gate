import json

import pytest

from soul_cradle.mcp_server import McpServer
from soul_cradle.mcp_server import main as mcp_main
from soul_cradle.plug import Gate, verify_ledger
from soul_cradle.policy import load_policy

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


PACK = {
    "pack": "test-law", "version": "1.0",
    "rules": [{"id": "residency", "assessor": "nemesis",
               "key": "data_residency", "op": "not_equals",
               "value": "on_premises", "severity": "critical",
               "finding": "Data must stay on premises."}],
}
BAD_PACK = {
    "pack": "bad-law", "version": "1.0",
    "rules": [{"id": "x", "assessor": "nobody", "key": "k",
               "op": "equals", "value": 1, "severity": "critical",
               "finding": "Nope."}],
}
OFF_PREMISES = dict(GOOD, data_residency="cloud_us")
ON_PREMISES = dict(GOOD, data_residency="on_premises")


def check_ids(payload):
    return [f["check_id"] for j in payload["judgments"]
            for f in j["findings"]]


def assess(s, arguments):
    reply = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "witness_gate_assess",
                                 "arguments": arguments}})
    return reply["result"]


def test_mcp_policy_pack_applied_via_server_config(tmp_path):
    ledger = str(tmp_path / "ledger.jsonl")
    s = McpServer(Gate(operator="test", ledger_path=ledger, policy=PACK))
    result = assess(s, {"action": "export", "evidence": OFF_PREMISES})
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["verdict"] == "blocked"
    assert "policy:test-law:residency" in check_ids(payload)
    assert payload["policy"]["pack"] == "test-law"
    assert payload["policy"]["sha256"] == load_policy(PACK).sha256
    result = assess(s, {"action": "export", "evidence": ON_PREMISES})
    payload = json.loads(result["content"][0]["text"])
    assert payload["verdict"] == "clear"
    with open(ledger) as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    assert entries and all(
        e["policy"]["pack"] == "test-law" for e in entries)
    assert verify_ledger(ledger) is True


def test_mcp_policy_pack_per_call():
    s = server()
    result = assess(s, {"action": "export", "evidence": OFF_PREMISES})
    payload = json.loads(result["content"][0]["text"])
    assert payload["verdict"] == "clear" and payload["policy"] is None
    result = assess(s, {"action": "export", "evidence": OFF_PREMISES,
                        "policy": PACK})
    payload = json.loads(result["content"][0]["text"])
    assert payload["verdict"] == "blocked"
    assert "policy:test-law:residency" in check_ids(payload)
    assert payload["policy"]["pack"] == "test-law"


def test_mcp_invalid_policy_pack_rejected():
    s = server()
    result = assess(s, {"action": "export", "evidence": OFF_PREMISES,
                        "policy": BAD_PACK})
    assert result["isError"] is True
    assert "unknown assessor" in result["content"][0]["text"]
    # A pack is never accepted as a file path.
    result = assess(s, {"action": "export", "evidence": OFF_PREMISES,
                        "policy": "customer-policy.json"})
    assert result["isError"] is True


def test_mcp_server_refuses_bad_policy_file(tmp_path):
    bad = tmp_path / "bad-pack.json"
    bad.write_text(json.dumps(BAD_PACK))
    with pytest.raises(SystemExit):
        mcp_main(["--policy", str(bad)])
    with pytest.raises(SystemExit):
        mcp_main(["--policy", str(tmp_path / "missing.json")])
