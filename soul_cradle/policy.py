"""Customer policy packs: bring your own law.

The gate ships with Mythara's rubric as the floor. The eight witnesses
judge every action against the built-in checks in assessors.py, and
that floor is not negotiable: no configuration weakens it.

A policy pack adds your organization's own rules on top of that floor,
as data, not code. A pack is a JSON file:

    {
      "pack": "harborlight-claims",
      "version": "1.0",
      "rules": [
        {
          "id": "data-residency",
          "assessor": "nemesis",
          "key": "data_residency",
          "op": "not_equals",
          "value": "on_premises",
          "severity": "critical",
          "finding": "Claimant data must stay on premises."
        }
      ]
    }

Each rule names one of the eight witnesses as its assessor, one
evidence key, one operator, and the severity its finding carries. When
a rule's condition matches the evidence packet, the witness it names
raises a finding, and the finding flows through the panel exactly like
a built-in one: a critical finding blocks, lesser findings flag or
contest, and the dissent is preserved. Policy findings are marked in
the result with check_id "policy:<pack>:<rule id>", so a reader can
always tell the customer's law from the built-in rubric.

Operators: equals, not_equals, in, not_in, exists, missing, gt, gte,
lt, lte, contains. "in" and "not_in" test the evidence value against
the rule's list value. "contains" tests whether the rule's value is
contained in the evidence value (a list, string, or mapping). "exists"
and "missing" take no value; consistent with the assessors, an
evidence key whose value is None counts as missing. Ordering
operators (gt, gte, lt, lte) match only when both sides are numbers.

The floor is not negotiable
---------------------------
A pack can only add findings. It can never suppress, clear, or
downgrade a built-in rubric finding, and there is no pack syntax for
removing or altering a built-in check. The three built-in criticals
(eros.deception, hermes.deception, nemesis.disproportion) block
regardless of any pack. A pack can tighten; it can never loosen.

Fail closed at configuration time
---------------------------------
Loading is strict. Malformed JSON, an unknown assessor, an unknown
operator, a bad severity, a duplicate rule id, or a missing or stray
"value" each raise PolicyError with a plain message. A Gate configured
with a pack that cannot load refuses to be constructed, so it can
never judge bare by accident: no law loaded, no judgments issued.

Provenance
----------
Packs are versioned, and every judgment a pack touches is sealed into
the ledger with the pack's identity: its name, its version, and the
sha256 of its canonical form (the parsed pack, keys sorted, compact
separators). The same pack content hashes identically whether it was
loaded from a file or a dict, so any sealed judgment can later be tied
to the exact law that was applied to it.

Standard library only, like the rest of the package.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from .assessors import ASSESSORS

OPERATORS = (
    "equals", "not_equals", "in", "not_in", "exists", "missing",
    "gt", "gte", "lt", "lte", "contains",
)
SEVERITIES = ("low", "medium", "high", "critical")

_VALUELESS_OPS = ("exists", "missing")
_LIST_VALUE_OPS = ("in", "not_in")

_ABSENT = object()
_MISSING = object()

_PACK_FIELDS = {"pack", "version", "rules"}
_RULE_FIELDS = {"id", "assessor", "key", "op", "value", "severity", "finding"}


class PolicyError(Exception):
    """A policy pack could not be loaded or failed validation."""


@dataclass(frozen=True)
class PolicyRule:
    """One customer rule: a condition over one evidence key."""

    rule_id: str
    assessor: str
    key: str
    op: str
    value: Any  # _ABSENT for exists/missing
    severity: str
    finding: str

    def condition_text(self) -> str:
        if self.op in _VALUELESS_OPS:
            return f"{self.key} {self.op}"
        return f"{self.key} {self.op} {self.value!r}"


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _rule_matches(rule: PolicyRule, evidence: Dict[str, Any]) -> bool:
    present = rule.key in evidence and evidence[rule.key] is not None
    if rule.op == "exists":
        return present
    if rule.op == "missing":
        return not present
    if not present:
        return False
    observed = evidence[rule.key]
    value = rule.value
    if rule.op == "equals":
        return observed == value
    if rule.op == "not_equals":
        return observed != value
    if rule.op == "in":
        return observed in value
    if rule.op == "not_in":
        return observed not in value
    if rule.op == "contains":
        try:
            return value in observed
        except TypeError:
            return False
    if rule.op in ("gt", "gte", "lt", "lte"):
        if not (_is_number(observed) and _is_number(value)):
            return False
        if rule.op == "gt":
            return observed > value
        if rule.op == "gte":
            return observed >= value
        if rule.op == "lt":
            return observed < value
        return observed <= value
    return False  # unreachable: op is validated at load


@dataclass(frozen=True)
class PolicyPack:
    """A validated policy pack, ready to evaluate."""

    name: str
    version: str
    rules: Tuple[PolicyRule, ...]
    sha256: str

    def identity(self) -> Dict[str, str]:
        """The provenance record sealed into ledger entries."""
        return {"pack": self.name, "version": self.version, "sha256": self.sha256}

    def evaluate(self, evidence: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Judge one evidence packet. Returns findings by assessor id.

        Only assessors with at least one matching rule appear in the
        result. Findings carry the same shape as built-in findings,
        with check_id "policy:<pack>:<rule id>" and the pack and rule
        named on the finding itself.
        """
        by_assessor: Dict[str, List[Dict[str, Any]]] = {}
        for rule in self.rules:
            if not _rule_matches(rule, evidence):
                continue
            observed = evidence.get(rule.key, _MISSING)
            by_assessor.setdefault(rule.assessor, []).append({
                "check_id": f"policy:{self.name}:{rule.rule_id}",
                "question": rule.finding,
                "finding": rule.finding,
                "severity": rule.severity,
                "observed": "<missing>" if observed is _MISSING else observed,
                "expected": f"condition matched: {rule.condition_text()}",
                "guidance": rule.finding,
                "policy_pack": self.name,
                "policy_rule": rule.rule_id,
            })
        return by_assessor


def _canonical_pack(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _validate_rule(raw: Any, pack_name: str, seen_ids: set) -> PolicyRule:
    where = f"pack {pack_name!r}"
    if not isinstance(raw, dict):
        raise PolicyError(f"{where}: each rule must be a JSON object")
    unknown = set(raw) - _RULE_FIELDS
    if unknown:
        raise PolicyError(
            f"{where}: rule has unknown field(s): {', '.join(sorted(unknown))}"
        )
    rule_id = raw.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise PolicyError(f"{where}: each rule needs a non-empty string 'id'")
    if rule_id in seen_ids:
        raise PolicyError(f"{where}: duplicate rule id {rule_id!r}")
    seen_ids.add(rule_id)
    assessor = raw.get("assessor")
    if assessor not in ASSESSORS:
        raise PolicyError(
            f"{where}: rule {rule_id!r} names unknown assessor {assessor!r}; "
            f"assessors are: {', '.join(sorted(ASSESSORS))}"
        )
    key = raw.get("key")
    if not isinstance(key, str) or not key.strip():
        raise PolicyError(
            f"{where}: rule {rule_id!r} needs a non-empty string 'key'"
        )
    op = raw.get("op")
    if op not in OPERATORS:
        raise PolicyError(
            f"{where}: rule {rule_id!r} names unknown op {op!r}; "
            f"operators are: {', '.join(OPERATORS)}"
        )
    severity = raw.get("severity")
    if severity not in SEVERITIES:
        raise PolicyError(
            f"{where}: rule {rule_id!r} has bad severity {severity!r}; "
            f"severities are: {', '.join(SEVERITIES)}"
        )
    finding = raw.get("finding")
    if not isinstance(finding, str) or not finding.strip():
        raise PolicyError(
            f"{where}: rule {rule_id!r} needs a non-empty string 'finding'"
        )
    if op in _VALUELESS_OPS:
        if "value" in raw:
            raise PolicyError(
                f"{where}: rule {rule_id!r} uses op {op!r}, which takes "
                "no 'value'; remove it"
            )
        value: Any = _ABSENT
    else:
        if "value" not in raw:
            raise PolicyError(
                f"{where}: rule {rule_id!r} uses op {op!r}, which "
                "requires a 'value'"
            )
        value = raw["value"]
        if op in _LIST_VALUE_OPS and not isinstance(value, list):
            raise PolicyError(
                f"{where}: rule {rule_id!r} uses op {op!r}, whose "
                "'value' must be a list"
            )
    return PolicyRule(
        rule_id=rule_id, assessor=assessor, key=key, op=op,
        value=value, severity=severity, finding=finding,
    )


def load_policy(source: Union[str, os.PathLike, Dict[str, Any], PolicyPack]) -> PolicyPack:
    """Load and strictly validate a policy pack.

    source: a path to a JSON pack file, a pack as a dict, or an
    already-loaded PolicyPack (returned unchanged).

    Raises PolicyError with a plain message on any problem: the file
    cannot be read, the JSON is malformed, or any field fails
    validation. Loading never fails silently.
    """
    if isinstance(source, PolicyPack):
        return source
    if isinstance(source, dict):
        obj: Any = source
    elif isinstance(source, (str, os.PathLike)):
        try:
            with open(source, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            raise PolicyError(
                f"cannot read policy pack file {os.fspath(source)!r}: {exc}"
            ) from exc
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PolicyError(
                f"policy pack file {os.fspath(source)!r} is not valid "
                f"JSON: {exc}"
            ) from exc
    else:
        raise PolicyError(
            "policy pack source must be a file path, a dict, or a "
            f"PolicyPack; got {type(source).__name__}"
        )

    if not isinstance(obj, dict):
        raise PolicyError("policy pack must be a JSON object")
    unknown = set(obj) - _PACK_FIELDS
    if unknown:
        raise PolicyError(
            f"policy pack has unknown field(s): {', '.join(sorted(unknown))}"
        )
    name = obj.get("pack")
    if not isinstance(name, str) or not name.strip():
        raise PolicyError("policy pack needs a non-empty string 'pack' name")
    version = obj.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PolicyError(
            f"pack {name!r} needs a non-empty string 'version'"
        )
    raw_rules = obj.get("rules")
    if not isinstance(raw_rules, list):
        raise PolicyError(f"pack {name!r}: 'rules' must be a list")
    seen_ids: set = set()
    rules = tuple(_validate_rule(r, name, seen_ids) for r in raw_rules)
    digest = hashlib.sha256(_canonical_pack(obj)).hexdigest()
    return PolicyPack(name=name, version=version, rules=rules, sha256=digest)
