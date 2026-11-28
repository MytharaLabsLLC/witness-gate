"""The ledger reader: verification verdicts and the readable report.

The properties under test are the ones the tool promises:

- an intact ledger verifies, through the library's own chain math;
- altering one entry breaks the chain at exactly that entry, and
  the reader and verify_ledger agree about it;
- a ledger that cannot be read at all exits with status 2;
- the report names the policy pack identity where one is recorded.
"""
import json

from soul_cradle.ledger_report import build_report, main, verdict_line
from soul_cradle.plug import Gate, verify_ledger, verify_ledger_detailed

GOOD = {
    "actor": "agent-1",
    "action_type": "send",
    "principal_consent": True,
    "affected_parties": ["customer"],
    "disproportionate_harm": False,
    "reversible": True,
    "precedent_setting": False,
    "fully_disclosed": True,
    "variance": "low",
    "deception_involved": False,
    "contradicts_commitments": False,
    "sustains_long_term": True,
    "hidden_costs_addressed": True,
    "safe_on_repetition": True,
    "strengthens_relationship": True,
}


def make_ledger(tmp_path, count=3):
    ledger = tmp_path / "ledger.jsonl"
    gate = Gate(operator="test", ledger_path=str(ledger))
    for n in range(count):
        gate.check(f"action {n}", dict(GOOD))
    return ledger


def test_intact_ledger_verifies_and_reports(tmp_path):
    ledger = make_ledger(tmp_path)
    report, detail = build_report(str(ledger))
    assert detail["ok"] is True
    assert detail["entries"] == 3
    assert detail["break_index"] is None
    assert verify_ledger(str(ledger)) is True
    assert "INTACT" in verdict_line(detail)
    assert "### Entry 2" in report
    assert main([str(ledger)]) == 0


def test_tampered_entry_breaks_at_that_entry(tmp_path):
    ledger = make_ledger(tmp_path)
    lines = ledger.read_text().splitlines()
    entry = json.loads(lines[1])
    entry["operator"] = "mallory"
    lines[1] = json.dumps(entry)
    ledger.write_text("\n".join(lines) + "\n")
    report, detail = build_report(str(ledger))
    assert detail["ok"] is False
    assert detail["break_index"] == 1
    assert "hash does not match" in detail["reason"]
    assert verify_ledger(str(ledger)) is False
    assert "BROKEN at entry 1" in verdict_line(detail)
    assert "CHAIN BREAK" in report
    assert main([str(ledger)]) == 1


def test_non_json_line_is_a_break(tmp_path):
    ledger = make_ledger(tmp_path)
    lines = ledger.read_text().splitlines()
    lines[2] = "{not json"
    ledger.write_text("\n".join(lines) + "\n")
    detail = verify_ledger_detailed(str(ledger))
    assert detail["ok"] is False
    assert detail["break_index"] == 2


def test_missing_ledger_exits_2(tmp_path):
    assert main([str(tmp_path / "nope.jsonl")]) == 2
