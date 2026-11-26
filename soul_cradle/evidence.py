"""Evidence that is derived, not just declared.

The panel judges the evidence it is given, so the honest question is
where the evidence comes from. This module derives what can be derived:

* Consent is looked up, not asserted. A ConsentBook is a small
  append-only record of who consented to what; `build_evidence` fills
  principal_consent from the book, so an agent cannot simply claim
  consent it never received.
* Reversibility is derived from the action type. Sending, deleting,
  paying, and publishing do not undo; drafting, previewing, and
  computing do. The table is a default, overridable per call.
* Affected parties are pulled from the call arguments (recipient,
  customer_id, user, account) instead of being restated by hand.

What cannot be derived (deception, disclosure, long-term effect) is
still supplied by the caller, and for every assessor the packet
engages, missing evidence fails closed when it is missing. (An
assessor is engaged once at least one of its evidence keys is
present; a packet that engages no assessor is cleared by universal
abstention.) Derivation narrows the caller's say; it does not remove
it.
"""

from __future__ import annotations

import json
import os
import time

IRREVERSIBLE = {
    "send", "send_email", "send_message", "delete", "remove", "pay",
    "charge", "refund", "transfer", "publish", "post", "deploy",
    "execute", "submit", "file", "cancel", "revoke", "sign",
}
REVERSIBLE = {
    "draft", "preview", "compute", "read", "list", "search", "plan",
    "create_draft", "simulate", "estimate", "check",
}
PARTY_KEYS = ("recipient", "customer_id", "customer", "user", "user_id",
              "account", "account_id", "principal", "to")


class ConsentBook:
    """Append-only consent record: who agreed to what, and when."""

    def __init__(self, path: str):
        self.path = path

    def record(self, principal: str, scope: str, note: str = "") -> dict:
        entry = {"principal": principal, "scope": scope,
                 "at": int(time.time()), "note": note}
        with open(self.path, "a") as fh:
            fh.write(json.dumps(entry) + "\n")
        return entry

    def has_consent(self, principal: str, scope: str) -> bool:
        if not os.path.exists(self.path):
            return False
        with open(self.path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if (entry.get("principal") == principal
                        and entry.get("scope") == scope):
                    return True
        return False


def derive_reversible(action_type: str) -> bool | None:
    verb = (action_type or "").lower().replace("-", "_")
    if verb in IRREVERSIBLE:
        return False
    if verb in REVERSIBLE:
        return True
    return None


def build_evidence(action_type: str, args: dict | None = None,
                   principal: str | None = None,
                   consent_book: ConsentBook | None = None,
                   consent_scope: str | None = None,
                   **facts) -> dict:
    """Assemble an evidence packet, deriving every derivable field.

    Explicit facts passed by the caller win over derived values, except
    consent: when a consent book and principal are given, consent comes
    from the book, never from the caller.
    """
    args = args or {}
    packet: dict = {}
    rev = derive_reversible(action_type)
    if rev is not None:
        packet["reversible"] = rev
    parties = [str(args[k]) for k in PARTY_KEYS if args.get(k)]
    if parties:
        packet["affected_parties"] = parties
    packet.update(facts)
    if consent_book is not None and principal is not None:
        packet["principal_consent"] = consent_book.has_consent(
            principal, consent_scope or action_type)
    packet["action_type"] = action_type
    return packet
