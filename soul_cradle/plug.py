"""Plug-and-play wiring for the Witness Gate.

The panel in assessors.py is the judgment core, but using it raw means
every integrator re-implements the same pattern by hand: build an
evidence packet, call the panel before the action runs, enforce the
verdict, and write the judgment somewhere tamper-evident.

This module is that pattern, written once:

    from soul_cradle.plug import Gate

    gate = Gate(operator="billing-service", ledger_path="gate-ledger.jsonl")

    @gate.action(evidence=lambda to, amount: {
        "principal_consent": True,
        "fully_disclosed": True,
        "reversible": amount < 500,
        "deception_involved": False,
    })
    def issue_refund(to, amount):
        ...

    issue_refund(to="customer-9", amount=120)   # judged first, then run

Enforcement, exactly as the panel defines it:

- "clear"     -> the action runs.
- "flagged"   -> the action does NOT run. HeldForReview is raised,
                 unless an on_hold callback is installed; the callback
                 is the human decision point and only its explicit True
                 lets the action run.
- "contested" -> same as flagged. The dissent is in the result.
- "blocked"   -> the action never runs. BlockedByGate is raised.
                 No callback can override a block: one critical witness
                 is enough, and the panel does not outvote it.

Every judgment, clears included, is appended to the ledger when a
ledger_path is configured. The ledger is a hash chain: each entry
carries the hash of the entry before it, so a quietly edited history
fails verify_ledger(). The chain proves the record is unaltered. It
does not prove the record is true.

Standard library only, like the rest of the package. Sync and async
functions are both supported.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import os
import time
from typing import Any, Callable, Dict, Optional, Union

from .assessors import (
    PANEL_BLOCKED,
    PANEL_CLEAR,
    PANEL_CONTESTED,
    PANEL_FLAGGED,
    PanelResult,
    panel,
)

EvidenceSource = Union[Dict[str, Any], Callable[..., Dict[str, Any]], None]


class GateBlocked(Exception):
    """A critical witness finding refused the action. It did not run."""

    def __init__(self, result: PanelResult, description: str):
        self.result = result
        self.description = description
        super().__init__(f"BLOCKED: {description} — {result.note}")


class HeldForReview(Exception):
    """The panel flagged or contested the action. It did not run.

    A human decides. Install an on_hold callback on the Gate to make
    that decision in code; without one, this exception is the hold.
    """

    def __init__(self, result: PanelResult, description: str):
        self.result = result
        self.description = description
        super().__init__(f"HELD ({result.verdict}): {description} — {result.note}")


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, default=str).encode()


class Gate:
    """A gate instance: one operator, one ledger, one hold policy."""

    def __init__(
        self,
        operator: str = "operator",
        ledger_path: Optional[str] = None,
        on_hold: Optional[Callable[[PanelResult, str], bool]] = None,
        default_evidence: Optional[Dict[str, Any]] = None,
        actor: Optional[str] = None,
        ledger: Optional[str] = None,
    ):
        self.operator = operator
        self.ledger_path = ledger_path if ledger_path is not None else ledger
        self.on_hold = on_hold
        self.default_evidence = dict(default_evidence or {})
        self.actor = actor
        self._last_hash = ""
        if self.ledger_path and os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        self._last_hash = json.loads(line).get("hash", "")

    # -- judgment ------------------------------------------------------

    def check(self, description: str, evidence: Dict[str, Any]) -> PanelResult:
        """Judge one proposed action and seal the judgment.

        Judgment only; enforcement lives in the decorator and in
        enforce(). Use this when the action is not a Python call you
        can wrap (an external tool call, a queued job, a workflow step).
        """
        merged = dict(self.default_evidence)
        merged.update(evidence or {})
        if self.actor and "actor" not in merged:
            merged["actor"] = self.actor
        result = panel(description, merged)
        self._seal(description, merged, result)
        return result

    def enforce(self, result: PanelResult, description: str) -> None:
        """Apply the verdict. Returns None to proceed; raises to stop."""
        if result.verdict == PANEL_CLEAR:
            return
        if result.verdict == PANEL_BLOCKED:
            raise GateBlocked(result, description)
        # flagged or contested: a human decides
        if self.on_hold is not None and self.on_hold(result, description):
            return
        raise HeldForReview(result, description)

    # -- the decorator --------------------------------------------------

    def action(
        self,
        evidence: EvidenceSource = None,
        describe: Optional[Union[str, Callable[..., str]]] = None,
        action_type: Optional[str] = None,
    ):
        """Wrap a function so the panel judges it before it runs.

        evidence: a dict, or a callable that receives the wrapped
            call's own arguments and returns the evidence dict.
        describe: the action description the witnesses hear. A string,
            a callable receiving the call's arguments, or None for an
            automatic "module.function(args)" description.
        action_type: fills evidence["action_type"] when the evidence
            does not set it.
        """

        def decorator(fn):
            def build_description(args, kwargs):
                if isinstance(describe, str):
                    return describe
                if callable(describe):
                    return describe(*args, **kwargs)
                parts = [repr(a) for a in args]
                parts += [f"{k}={v!r}" for k, v in kwargs.items()]
                joined = ", ".join(parts)
                if len(joined) > 160:
                    joined = joined[:157] + "..."
                return f"{fn.__qualname__}({joined})"

            def build_evidence(args, kwargs):
                ev = dict(evidence(*args, **kwargs)) if callable(evidence) \
                    else dict(evidence or {})
                if action_type and "action_type" not in ev:
                    ev["action_type"] = action_type
                return ev

            if inspect.iscoroutinefunction(fn):
                @functools.wraps(fn)
                async def awrapped(*args, **kwargs):
                    description = build_description(args, kwargs)
                    result = self.check(description, build_evidence(args, kwargs))
                    self.enforce(result, description)
                    return await fn(*args, **kwargs)

                return awrapped

            @functools.wraps(fn)
            def wrapped(*args, **kwargs):
                description = build_description(args, kwargs)
                result = self.check(description, build_evidence(args, kwargs))
                self.enforce(result, description)
                return fn(*args, **kwargs)

            return wrapped

        return decorator

    # -- the sealed ledger ----------------------------------------------

    def _seal(self, description: str, evidence: Dict[str, Any],
              result: PanelResult) -> None:
        if not self.ledger_path:
            return
        entry = {
            "ts": int(time.time()),
            "operator": self.operator,
            "action": description,
            "evidence": evidence,
            "result": result.to_dict(),
            "prev_hash": self._last_hash,
        }
        entry["hash"] = hashlib.sha256(
            self._last_hash.encode() + _canonical(entry)
        ).hexdigest()
        with open(self.ledger_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
        self._last_hash = entry["hash"]


def verify_ledger(ledger_path: str) -> bool:
    """Recompute the hash chain. False means the record was altered."""
    prev = ""
    with open(ledger_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("prev_hash") != prev:
                return False
            claimed = entry.get("hash", "")
            body = {k: v for k, v in entry.items() if k != "hash"}
            actual = hashlib.sha256(prev.encode() + _canonical(body)).hexdigest()
            if actual != claimed:
                return False
            prev = claimed
    return True
