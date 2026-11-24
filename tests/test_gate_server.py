import http.client
import json
import threading

import pytest

from soul_cradle.gate_server import serve
from soul_cradle.plug import Gate

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
