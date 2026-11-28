import http.client
import json
import threading

import pytest

from soul_cradle.gate_server import main as gate_main
from soul_cradle.gate_server import serve
from soul_cradle.plug import Gate, verify_ledger
from soul_cradle.policy import load_policy

GOOD = {"principal_consent": True, "fully_disclosed": True,
        "reversible": True, "deception_involved": False,
        "affected_parties": ["customer"], "disproportionate_harm": False,
        "contradicts_commitments": False, "sustains_long_term": True,
        "hidden_costs_addressed": True, "safe_on_repetition": True,
        "strengthens_relationship": True, "precedent_setting": False,
        "variance": "low", "actor": "agent-7", "action_type": "refund"}


@pytest.fixture()
def server():
    srv = serve("127.0.0.1", 0, Gate(operator="test"))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv.server_address[1]
    srv.shutdown()


def call(port, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(body) if body is not None else None
    conn.request(method, path, payload,
                 {"Content-Type": "application/json"} if payload else {})
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    return resp.status, data


def test_health(server):
    status, data = call(server, "GET", "/health")
    assert status == 200 and data["ok"] is True


def test_assess_clear_and_blocked(server):
    status, data = call(server, "POST", "/assess",
                        {"action": "refund", "evidence": GOOD})
    assert status == 200 and data["verdict"] == "clear"
    bad = dict(GOOD, deception_involved=True)
    status, data = call(server, "POST", "/assess",
                        {"action": "deceive", "evidence": bad})
    assert status == 200 and data["verdict"] == "blocked"


def test_bad_body_is_400(server):
    status, _ = call(server, "POST", "/assess", {"evidence": {}})
    assert status == 400


def test_rubrics_lists_eight(server):
    status, data = call(server, "GET", "/rubrics")
    assert status == 200 and len(data["rubrics"]) == 8


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


@pytest.fixture()
def policy_server(tmp_path):
    ledger = str(tmp_path / "ledger.jsonl")
    gate = Gate(operator="test", ledger_path=ledger, policy=PACK)
    srv = serve("127.0.0.1", 0, gate)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv.server_address[1], ledger
    srv.shutdown()


def test_policy_pack_applied_via_server_config(policy_server):
    port, ledger = policy_server
    status, data = call(port, "POST", "/assess",
                        {"action": "export", "evidence": OFF_PREMISES})
    assert status == 200 and data["verdict"] == "blocked"
    assert "policy:test-law:residency" in check_ids(data)
    assert data["policy"]["pack"] == "test-law"
    assert data["policy"]["version"] == "1.0"
    assert data["policy"]["sha256"] == load_policy(PACK).sha256
    status, data = call(port, "POST", "/assess",
                        {"action": "export", "evidence": ON_PREMISES})
    assert status == 200 and data["verdict"] == "clear"
    with open(ledger) as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    assert entries and all(
        e["policy"]["sha256"] == load_policy(PACK).sha256 for e in entries)
    assert verify_ledger(ledger) is True


def test_policy_endpoint_reports_server_pack(policy_server, server):
    port, _ledger = policy_server
    status, data = call(port, "GET", "/policy")
    assert status == 200 and data["policy"]["pack"] == "test-law"
    status, data = call(server, "GET", "/policy")
    assert status == 200 and data["policy"] is None


def test_policy_pack_per_request(tmp_path):
    ledger = str(tmp_path / "ledger.jsonl")
    srv = serve("127.0.0.1", 0, Gate(operator="test", ledger_path=ledger))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        port = srv.server_address[1]
        # Without a pack, the same evidence clears.
        status, data = call(port, "POST", "/assess",
                            {"action": "export", "evidence": OFF_PREMISES})
        assert status == 200 and data["verdict"] == "clear"
        assert data["policy"] is None
        # With a per-request pack it blocks, under the pack's own id.
        status, data = call(port, "POST", "/assess",
                            {"action": "export", "evidence": OFF_PREMISES,
                             "policy": PACK})
        assert status == 200 and data["verdict"] == "blocked"
        assert "policy:test-law:residency" in check_ids(data)
        assert data["policy"]["pack"] == "test-law"
    finally:
        srv.shutdown()
    with open(ledger) as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    assert "policy" not in entries[0]
    assert entries[1]["policy"]["pack"] == "test-law"
    assert verify_ledger(ledger) is True


def test_invalid_policy_pack_rejected(server):
    status, data = call(server, "POST", "/assess",
                        {"action": "export", "evidence": OFF_PREMISES,
                         "policy": BAD_PACK})
    assert status == 400 and "unknown assessor" in data["error"]
    # A pack is never accepted as a file path.
    status, data = call(server, "POST", "/assess",
                        {"action": "export", "evidence": OFF_PREMISES,
                         "policy": "customer-policy.json"})
    assert status == 400


def test_gate_server_refuses_bad_policy_file(tmp_path):
    bad = tmp_path / "bad-pack.json"
    bad.write_text(json.dumps(BAD_PACK))
    with pytest.raises(SystemExit):
        gate_main(["--policy", str(bad)])
    with pytest.raises(SystemExit):
        gate_main(["--policy", str(tmp_path / "missing.json")])
