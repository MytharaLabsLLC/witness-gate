"""Customer policy packs: loading, evaluation, the floor, the ledger.

The properties under test are the ones the feature promises:

- a valid pack loads, from a file or a dict, with a stable hash;
- every operator behaves, and validation is strict (PolicyError,
  never a silent pass);
- a Gate configured with an unloadable pack refuses to judge;
- a policy critical blocks an action the built-in rubric clears;
- no pack rescues or downgrades a built-in finding (the floor);
- policy findings are marked with the pack id in the result;
- sealed entries record the pack identity, ledgers written before
  the policy layer still verify, policy-era entries verify, and
  tampering with a policy-era entry is still detected.
"""

import json
import shutil
from pathlib import Path

import pytest

from soul_cradle.assessors import panel
from soul_cradle.plug import Gate, GateBlocked, verify_ledger
from soul_cradle.policy import PolicyError, PolicyPack, load_policy

FIXTURE_LEDGER = (
    Path(__file__).parent / "fixtures" / "pre_policy_ledger.jsonl"
)

CLEAN = {
    "principal_consent": True, "fully_disclosed": True,
    "reversible": True, "deception_involved": False,
    "affected_parties": ["customer-1"], "disproportionate_harm": False,
    "contradicts_commitments": False, "sustains_long_term": True,
    "hidden_costs_addressed": True, "safe_on_repetition": True,
    "strengthens_relationship": True, "precedent_setting": False,
    "variance": "low",
}


def pack_dict(**overrides):
    base = {
        "pack": "test-pack",
        "version": "1.0",
        "rules": [
            {"id": "residency", "assessor": "nemesis",
             "key": "data_residency", "op": "not_equals",
             "value": "on_premises", "severity": "critical",
             "finding": "Data must stay on premises."},
        ],
    }
    base.update(overrides)
    return base


_ABSENT = object()


def one_rule_pack(op, value_marker, key="k"):
    rule = {"id": "r1", "assessor": "janus", "key": key, "op": op,
            "severity": "high", "finding": "Rule r1 fired."}
    if value_marker is not _ABSENT:
        rule["value"] = value_marker
    return load_policy({"pack": "ops", "version": "0.1", "rules": [rule]})


def fires(pack, evidence):
    return bool(pack.evaluate(evidence).get("janus"))


# ---------------------------------------------------------------------------
# Loading and validation
# ---------------------------------------------------------------------------


def test_valid_pack_loads_from_dict_and_file(tmp_path):
    from_dict = load_policy(pack_dict())
    assert isinstance(from_dict, PolicyPack)
    assert from_dict.name == "test-pack"
    assert from_dict.version == "1.0"
    assert len(from_dict.rules) == 1

    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack_dict(), indent=2), encoding="utf-8")
    from_file = load_policy(str(path))
    # Same content, different formatting: same canonical hash.
    assert from_file.sha256 == from_dict.sha256
    assert from_file.identity() == {
        "pack": "test-pack", "version": "1.0", "sha256": from_dict.sha256,
    }
    # A loaded pack passes through unchanged.
    assert load_policy(from_dict) is from_dict


def test_malformed_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(str(path))


def test_missing_file_raises():
    with pytest.raises(PolicyError):
        load_policy("/nonexistent/no-such-pack.json")


def test_unknown_assessor_raises():
    bad = pack_dict()
    bad["rules"][0]["assessor"] = "zeus"
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_unknown_op_raises():
    bad = pack_dict()
    bad["rules"][0]["op"] = "resembles"
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_bad_severity_raises():
    bad = pack_dict()
    bad["rules"][0]["severity"] = "extreme"
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_duplicate_rule_id_raises():
    bad = pack_dict()
    bad["rules"].append(dict(bad["rules"][0]))
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_value_misuse_raises():
    # exists takes no value
    bad = pack_dict()
    bad["rules"][0].update({"op": "exists", "value": "on_premises"})
    with pytest.raises(PolicyError):
        load_policy(bad)
    # equals requires a value
    bad2 = pack_dict()
    del bad2["rules"][0]["value"]
    with pytest.raises(PolicyError):
        load_policy(bad2)
    # in requires a list value
    bad3 = pack_dict()
    bad3["rules"][0].update({"op": "in", "value": "on_premises"})
    with pytest.raises(PolicyError):
        load_policy(bad3)


def test_gate_with_unloadable_pack_refuses_to_judge():
    with pytest.raises(PolicyError):
        Gate(policy="/nonexistent/no-such-pack.json")
    bad = pack_dict()
    bad["rules"][0]["assessor"] = "nobody"
    with pytest.raises(PolicyError):
        Gate(policy=bad)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


def test_each_operator_behaves():
    assert fires(one_rule_pack("equals", "a"), {"k": "a"})
    assert not fires(one_rule_pack("equals", "a"), {"k": "b"})
    assert not fires(one_rule_pack("equals", "a"), {})

    assert fires(one_rule_pack("not_equals", "a"), {"k": "b"})
    assert not fires(one_rule_pack("not_equals", "a"), {"k": "a"})
    assert not fires(one_rule_pack("not_equals", "a"), {})

    assert fires(one_rule_pack("in", ["x", "y"]), {"k": "x"})
    assert not fires(one_rule_pack("in", ["x", "y"]), {"k": "z"})

    assert fires(one_rule_pack("not_in", ["x", "y"]), {"k": "z"})
    assert not fires(one_rule_pack("not_in", ["x", "y"]), {"k": "x"})

    assert fires(one_rule_pack("exists", _ABSENT), {"k": 0})
    assert not fires(one_rule_pack("exists", _ABSENT), {})
    assert not fires(one_rule_pack("exists", _ABSENT), {"k": None})

    assert fires(one_rule_pack("missing", _ABSENT), {})
    assert fires(one_rule_pack("missing", _ABSENT), {"k": None})
    assert not fires(one_rule_pack("missing", _ABSENT), {"k": "v"})

    assert fires(one_rule_pack("gt", 10), {"k": 11})
    assert not fires(one_rule_pack("gt", 10), {"k": 10})
    assert fires(one_rule_pack("gte", 10), {"k": 10})
    assert not fires(one_rule_pack("gte", 10), {"k": 9})
    assert fires(one_rule_pack("lt", 10), {"k": 9})
    assert not fires(one_rule_pack("lt", 10), {"k": 10})
    assert fires(one_rule_pack("lte", 10), {"k": 10})
    assert not fires(one_rule_pack("lte", 10), {"k": 11})
    # Ordering operators never match on non-numbers.
    assert not fires(one_rule_pack("gt", 10), {"k": "lots"})

    assert fires(one_rule_pack("contains", "b"), {"k": ["a", "b"]})
    assert not fires(one_rule_pack("contains", "c"), {"k": ["a", "b"]})
    assert fires(one_rule_pack("contains", "ell"), {"k": "hello"})
    assert not fires(one_rule_pack("contains", "z"), {"k": 42})


# ---------------------------------------------------------------------------
# The panel and the floor
# ---------------------------------------------------------------------------


def test_policy_critical_blocks_what_builtin_clears():
    ev = dict(CLEAN, data_residency="cloud_us")
    assert panel("export", ev).verdict == "clear"

    result = panel("export", ev, policy=load_policy(pack_dict()))
    assert result.verdict == "blocked"
    nemesis = [j for j in result.judgments if j.assessor_id == "nemesis"][0]
    assert nemesis.verdict == "flagged"
    policy_findings = [
        f for f in nemesis.findings
        if f["check_id"] == "policy:test-pack:residency"
    ]
    assert len(policy_findings) == 1
    assert policy_findings[0]["severity"] == "critical"
    assert policy_findings[0]["policy_pack"] == "test-pack"
    assert policy_findings[0]["policy_rule"] == "residency"


def test_policy_engages_an_abstaining_witness():
    # data_residency is not a built-in key: every witness abstains and
    # the bare panel clears by universal abstention. The customer's
    # law engages nemesis, and its critical blocks.
    ev = {"data_residency": "cloud_us"}
    assert panel("export", ev).verdict == "clear"
    result = panel("export", ev, policy=load_policy(pack_dict()))
    assert result.verdict == "blocked"


def test_pack_cannot_rescue_a_builtin_critical():
    permissive = load_policy({
        "pack": "permissive", "version": "0.1",
        "rules": [
            {"id": "note-large", "assessor": "janus", "key": "amount",
             "op": "gt", "value": 1000000, "severity": "low",
             "finding": "Very large amount."},
        ],
    })
    ev = dict(CLEAN, deception_involved=True, amount=5)
    result = panel("deceptive action", ev, policy=permissive)
    assert result.verdict == "blocked"
    eros = [j for j in result.judgments if j.assessor_id == "eros"][0]
    check_ids = [f["check_id"] for f in eros.findings]
    assert "eros.deception" in check_ids


def test_pack_cannot_downgrade_a_builtin_finding():
    ev = dict(CLEAN, variance="high")  # dionysus.variance, high, built-in
    bare = panel("risky action", ev)
    with_pack = panel("risky action", ev, policy=load_policy(pack_dict()))
    assert with_pack.verdict == bare.verdict != "clear"
    bare_dionysus = [
        j for j in bare.judgments if j.assessor_id == "dionysus"
    ][0]
    pack_dionysus = [
        j for j in with_pack.judgments if j.assessor_id == "dionysus"
    ][0]
    assert pack_dionysus.findings == bare_dionysus.findings
    assert pack_dionysus.findings[0]["severity"] == "high"


def test_policy_low_finding_flows_through_panel_logic():
    low = load_policy({
        "pack": "watchful", "version": "1.0",
        "rules": [
            {"id": "big-amount", "assessor": "hermes", "key": "amount",
             "op": "gt", "value": 100, "severity": "low",
             "finding": "Amount over 100, noted."},
        ],
    })
    ev = dict(CLEAN, amount=250)
    result = panel("transfer", ev, policy=low)
    # One witness flagged by policy, the rest clear: contested, with
    # the dissent naming the policy finding.
    assert result.verdict == "contested"
    assert result.dissent[0]["flagged_by"] == "hermes"
    assert result.dissent[0]["finding"]["check_id"] == (
        "policy:watchful:big-amount"
    )


def test_gate_enforce_raises_gateblocked_on_policy_critical(tmp_path):
    gate = Gate(
        ledger_path=str(tmp_path / "ledger.jsonl"),
        policy=pack_dict(),
    )
    result = gate.check("export", dict(CLEAN, data_residency="cloud_us"))
    assert result.verdict == "blocked"
    with pytest.raises(GateBlocked):
        gate.enforce(result, "export")


# ---------------------------------------------------------------------------
# The sealed record
# ---------------------------------------------------------------------------


def test_sealed_entry_records_pack_identity(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    pack = load_policy(pack_dict())
    gate = Gate(ledger_path=str(ledger), policy=pack)
    gate.check("export", dict(CLEAN, data_residency="on_premises"))
    entry = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    assert entry["policy"] == {
        "pack": "test-pack", "version": "1.0", "sha256": pack.sha256,
    }
    assert verify_ledger(str(ledger))


def test_entry_without_pack_has_no_policy_key(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    Gate(ledger_path=str(ledger)).check("export", dict(CLEAN))
    entry = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    assert "policy" not in entry
    assert verify_ledger(str(ledger))


def test_pre_change_ledger_still_verifies(tmp_path):
    ledger = tmp_path / "old.jsonl"
    shutil.copy(FIXTURE_LEDGER, ledger)
    assert verify_ledger(str(ledger))
    entries = [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(entries) == 2
    assert all("policy" not in e for e in entries)


def test_policy_ledger_verifies_and_tamper_is_detected(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    gate = Gate(ledger_path=str(ledger), policy=pack_dict())
    gate.check("export", dict(CLEAN, data_residency="on_premises"))
    gate.check("export", dict(CLEAN, data_residency="cloud_us"))
    assert verify_ledger(str(ledger))

    lines = ledger.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["policy"]["version"] = "9.9"
    lines[1] = json.dumps(tampered)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not verify_ledger(str(ledger))


def test_chain_continues_across_the_policy_boundary(tmp_path):
    # A ledger begun before the policy layer gains a policy-era entry:
    # the chain continues from the pre-change hash and still verifies.
    ledger = tmp_path / "mixed.jsonl"
    shutil.copy(FIXTURE_LEDGER, ledger)
    gate = Gate(ledger_path=str(ledger), policy=pack_dict())
    gate.check("export", dict(CLEAN, data_residency="on_premises"))
    assert verify_ledger(str(ledger))
    entries = [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(entries) == 3
    assert "policy" not in entries[0]
    assert entries[2]["policy"]["pack"] == "test-pack"
