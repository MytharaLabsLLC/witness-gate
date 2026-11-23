"""Tests for soul_cradle.plug, the plug-and-play wrapper.

Verdict fixtures were verified against the live panel before being
written here: the full favorable evidence set clears, adding deception
blocks (Eros critical), a sparse packet flags, and the four-key packet
from the README contests.
"""
import asyncio
import json

import pytest

from soul_cradle.plug import Gate, GateBlocked, HeldForReview, verify_ledger

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


def read_ledger(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_clear_action_runs_and_seals(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    gate = Gate(operator="test", ledger_path=str(ledger))
    ran = []

    @gate.action(evidence=dict(GOOD))
    def send_report(to):
        ran.append(to)
        return f"sent to {to}"

    assert send_report("customer-9") == "sent to customer-9"
    assert ran == ["customer-9"]
    entries = read_ledger(ledger)
    assert len(entries) == 1
    assert entries[0]["result"]["verdict"] == "clear"
    assert verify_ledger(str(ledger)) is True


def test_blocked_action_never_runs(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    gate = Gate(operator="test", ledger_path=str(ledger))
    ran = []
    bad = dict(GOOD)
    bad["deception_involved"] = True

    @gate.action(evidence=bad)
    def send_report(to):
        ran.append(to)

    with pytest.raises(GateBlocked) as exc:
        send_report("customer-9")
    assert ran == []
    assert exc.value.result.verdict == "blocked"
    # the block itself is sealed in the record
    entries = read_ledger(ledger)
    assert entries[0]["result"]["verdict"] == "blocked"
    assert verify_ledger(str(ledger)) is True


def test_flagged_action_is_held_by_default():
    gate = Gate(operator="test")

    @gate.action(evidence={"principal_consent": True})
    def send_report(to):
        return "ran"

    with pytest.raises(HeldForReview) as exc:
        send_report("customer-9")
    assert exc.value.result.verdict == "flagged"


def test_on_hold_true_is_the_human_yes():
    seen = []
    gate = Gate(operator="test",
                on_hold=lambda result, desc: seen.append(result.verdict) or True)

    @gate.action(evidence={"principal_consent": True,
                            "fully_disclosed": True,
                            "reversible": True,
                            "deception_involved": False})
    def send_report(to):
        return "ran"

    # the four-key packet contests; the human callback says proceed
    assert send_report("customer-9") == "ran"
    assert seen == ["contested"]


def test_on_hold_cannot_override_a_block():
    gate = Gate(operator="test", on_hold=lambda result, desc: True)
    bad = dict(GOOD)
    bad["deception_involved"] = True

    @gate.action(evidence=bad)
    def send_report(to):
        return "ran"

    with pytest.raises(GateBlocked):
        send_report("customer-9")


def test_evidence_callable_receives_call_arguments():
    gate = Gate(operator="test")

    @gate.action(evidence=lambda to, amount: dict(
        GOOD, reversible=amount < 500, action_type="refund"))
    def issue_refund(to, amount):
        return f"refunded {amount} to {to}"

    assert issue_refund("customer-9", 120) == "refunded 120 to customer-9"


def test_async_action_is_wrapped():
    gate = Gate(operator="test")

    @gate.action(evidence=dict(GOOD))
    async def send_report(to):
        return f"sent to {to}"

    assert asyncio.run(send_report("customer-9")) == "sent to customer-9"


def test_check_judges_without_a_function(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    gate = Gate(operator="test", ledger_path=str(ledger))
    result = gate.check("External tool call: post to public feed", dict(GOOD))
    assert result.verdict == "clear"
    assert read_ledger(ledger)[0]["action"].startswith("External tool call")


def test_ledger_tampering_fails_verification(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    gate = Gate(operator="test", ledger_path=str(ledger))

    @gate.action(evidence=dict(GOOD))
    def send_report(to):
        return "ok"

    send_report("a")
    send_report("b")
    assert verify_ledger(str(ledger)) is True
    lines = ledger.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["result"]["verdict"] = "blocked"  # quietly rewrite history
    lines[0] = json.dumps(entry)
    ledger.write_text("\n".join(lines) + "\n")
    assert verify_ledger(str(ledger)) is False
