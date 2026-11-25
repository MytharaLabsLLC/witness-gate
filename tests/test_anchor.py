"""Tests for soul_cradle.anchor, the ledger anchoring option.

The centerpiece is the full-rewrite attack: the ledger's hash chain
alone cannot catch an attacker who regenerates the whole chain from
scratch, because verification only asks whether the file agrees with
itself. These tests prove the chain alone is fooled, and that a signed
anchor is not.
"""
import hashlib
import json
import os
import stat

import pytest

from soul_cradle.anchor import (
    AnchorError,
    anchors_path_for,
    create_anchor,
    generate_key,
    load_key,
    main,
    read_anchors,
    verify_anchors,
)
from soul_cradle.plug import Gate, verify_ledger

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

KEY = bytes.fromhex(generate_key())
OTHER_KEY = bytes.fromhex(generate_key())


def make_ledger(tmp_path, n=3):
    ledger = tmp_path / "ledger.jsonl"
    gate = Gate(operator="test", ledger_path=str(ledger))

    @gate.action(evidence=dict(GOOD))
    def send_report(to):
        return f"sent to {to}"

    for i in range(n):
        send_report(f"customer-{i}")
    return ledger


def rewrite_chain(path, mutate):
    """Regenerate the whole hash chain after mutating the entries.

    This is the attack the chain alone cannot see: the rewritten file
    is internally consistent, so verify_ledger returns True for it.
    """
    entries = [json.loads(line)
               for line in path.read_text().splitlines() if line.strip()]
    mutate(entries)
    prev = ""
    out = []
    for e in entries:
        e["prev_hash"] = prev
        body = {k: v for k, v in e.items() if k != "hash"}
        e["hash"] = hashlib.sha256(
            prev.encode()
            + json.dumps(body, sort_keys=True, default=str).encode()
        ).hexdigest()
        prev = e["hash"]
        out.append(json.dumps(e, default=str))
    path.write_text("\n".join(out) + "\n")


def test_anchor_roundtrip(tmp_path):
    ledger = make_ledger(tmp_path, 3)
    record = create_anchor(str(ledger), KEY)
    assert record["entries"] == 3
    ok, details = verify_anchors(str(ledger), KEY)
    assert ok, details
    assert details["anchored_entries"] == 3
    assert details["unanchored_tail"] == 0


def test_second_anchor_chains_to_first(tmp_path):
    ledger = make_ledger(tmp_path, 2)
    first = create_anchor(str(ledger), KEY)
    gate = Gate(operator="test", ledger_path=str(ledger))

    @gate.action(evidence=dict(GOOD))
    def send_report(to):
        return f"sent to {to}"

    send_report("customer-9")
    second = create_anchor(str(ledger), KEY)
    assert second["prev_anchor"] == first["anchor_hash"]
    ok, details = verify_anchors(str(ledger), KEY)
    assert ok, details
    assert details["anchors"] == 2


def test_unanchored_tail_reported_not_failed(tmp_path):
    ledger = make_ledger(tmp_path, 1)
    create_anchor(str(ledger), KEY)
    gate = Gate(operator="test", ledger_path=str(ledger))

    @gate.action(evidence=dict(GOOD))
    def send_report(to):
        return f"sent to {to}"

    send_report("customer-1")
    send_report("customer-2")
    ok, details = verify_anchors(str(ledger), KEY)
    assert ok, details
    assert details["anchored_entries"] == 1
    assert details["unanchored_tail"] == 2


def test_full_rewrite_attack_fools_chain_but_not_anchor(tmp_path):
    ledger = make_ledger(tmp_path, 3)
    create_anchor(str(ledger), KEY)

    def steal(entries):
        entries[0]["action"] = "Send report to attacker instead"

    rewrite_chain(ledger, steal)
    # The chain alone is fooled: the rewritten file agrees with itself.
    assert verify_ledger(str(ledger)) is True
    # The signed anchor is not.
    ok, details = verify_anchors(str(ledger), KEY)
    assert not ok
    assert any("rewritten" in f for f in details["failures"])


def test_tampered_entry_breaks_chain_and_anchor_refuses(tmp_path):
    ledger = make_ledger(tmp_path, 2)
    lines = ledger.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["action"] = "quietly edited"
    lines[0] = json.dumps(entry, default=str)
    ledger.write_text("\n".join(lines) + "\n")
    assert verify_ledger(str(ledger)) is False
    with pytest.raises(AnchorError):
        create_anchor(str(ledger), KEY)


def test_truncated_ledger_caught(tmp_path):
    ledger = make_ledger(tmp_path, 3)
    create_anchor(str(ledger), KEY)
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines[:-1]) + "\n")
    # Dropping the tail keeps the remaining chain internally valid...
    assert verify_ledger(str(ledger)) is True
    # ...but the anchor counted three entries.
    ok, details = verify_anchors(str(ledger), KEY)
    assert not ok
    assert any("truncated" in f for f in details["failures"])


def test_forged_anchor_rejected(tmp_path):
    ledger = make_ledger(tmp_path, 2)
    real = create_anchor(str(ledger), KEY)
    body = {
        "version": "1",
        "ledger": "ledger.jsonl",
        "entries": 2,
        "head": real["head"],
        "ts": 1999999999,
        "prev_anchor": real["anchor_hash"],
    }
    forged = dict(body)
    forged["anchor_hash"] = hashlib.sha256(
        body["prev_anchor"].encode()
        + json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()
    forged["signature"] = "0" * 64
    with open(anchors_path_for(str(ledger)), "a") as fh:
        fh.write(json.dumps(forged) + "\n")
    ok, details = verify_anchors(str(ledger), KEY)
    assert not ok
    assert any("signature" in f for f in details["failures"])
    with pytest.raises(AnchorError):
        create_anchor(str(ledger), KEY)


def test_wrong_key_fails(tmp_path):
    ledger = make_ledger(tmp_path, 2)
    create_anchor(str(ledger), KEY)
    ok, details = verify_anchors(str(ledger), OTHER_KEY)
    assert not ok
    assert any("signature" in f for f in details["failures"])
    with pytest.raises(AnchorError):
        create_anchor(str(ledger), OTHER_KEY)


def test_no_anchors_is_not_ok(tmp_path):
    ledger = make_ledger(tmp_path, 1)
    ok, details = verify_anchors(str(ledger), KEY)
    assert not ok
    assert any("no anchors" in f for f in details["failures"])


def test_empty_ledger_anchor_refused(tmp_path):
    ledger = tmp_path / "empty.jsonl"
    ledger.write_text("")
    with pytest.raises(AnchorError):
        create_anchor(str(ledger), KEY)


def test_key_loading(tmp_path, monkeypatch):
    key_file = tmp_path / "anchor.key"
    key_file.write_text(generate_key() + "\n")
    assert len(load_key(str(key_file))) == 32
    monkeypatch.setenv("WITNESS_GATE_ANCHOR_KEY", generate_key())
    assert len(load_key()) == 32
    monkeypatch.delenv("WITNESS_GATE_ANCHOR_KEY")
    with pytest.raises(AnchorError):
        load_key()


def test_cli_roundtrip(tmp_path):
    ledger = make_ledger(tmp_path, 2)
    key_file = tmp_path / "anchor.key"
    assert main(["init-key", "--key-file", str(key_file)]) == 0
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600
    # Refuses to overwrite an existing key.
    assert main(["init-key", "--key-file", str(key_file)]) == 2
    assert main(["create", str(ledger), "--key-file", str(key_file)]) == 0
    assert main(["verify", str(ledger), "--key-file", str(key_file)]) == 0
    assert main(["show", str(ledger)]) == 0
    anchors = read_anchors(anchors_path_for(str(ledger)))
    assert len(anchors) == 1
