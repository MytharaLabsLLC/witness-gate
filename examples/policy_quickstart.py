"""Bring your own law: the gate, plus a customer policy pack.

Runs the fictional Harborlight Claims Co. pack
(examples/customer-policy.json) end to end:

1. A compliant export clears: the built-in rubric is satisfied and
   no policy rule fires.
2. The same export with data moved off premises is BLOCKED by the
   customer's own rule (critical, under nemesis), even though the
   built-in rubric alone clears it.
3. A deceptive action is BLOCKED by the built-in floor. The pack has
   no deception rule and offers no rescue: a pack can tighten, never
   loosen.

Every judgment is sealed into a ledger that records the pack's name,
version, and sha256, and the ledger verifies at the end.

Run: python3 examples/policy_quickstart.py
"""
import os
import tempfile

from soul_cradle import Gate, GateBlocked, verify_ledger

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_PATH = os.path.join(HERE, "customer-policy.json")

ledger_path = os.path.join(tempfile.mkdtemp(), "policy-ledger.jsonl")
gate = Gate(
    operator="harborlight-claims",
    ledger_path=ledger_path,
    policy=PACK_PATH,
)


def export_evidence(**overrides):
    """A clean built-in packet, plus the keys Harborlight's law reads."""
    ev = {
        "principal_consent": True, "fully_disclosed": True,
        "reversible": True, "deception_involved": False,
        "affected_parties": ["claimant-41"], "disproportionate_harm": False,
        "contradicts_commitments": False, "sustains_long_term": True,
        "hidden_costs_addressed": True, "safe_on_repetition": True,
        "strengthens_relationship": True, "precedent_setting": False,
        "variance": "low",
        "data_residency": "on_premises", "amount": 250,
        "consent_reference": "consent-2026-1187",
        "destination_country": "US",
    }
    ev.update(overrides)
    return ev


@gate.action(evidence=lambda **kw: export_evidence(**kw))
def export_claim_summary(**kw):
    return "export written"


# 1. Compliant: clears and runs.
print("1.", export_claim_summary())

# 2. Off premises: the customer's own law blocks it.
try:
    export_claim_summary(data_residency="cloud_us")
    print("2. UNEXPECTED: the off-premises export ran")
except GateBlocked as blocked:
    print("2. BLOCKED by customer policy:", blocked.result.note)

# 3. Deceptive: the built-in floor blocks it; the pack cannot rescue it.
try:
    export_claim_summary(deception_involved=True)
    print("3. UNEXPECTED: the deceptive export ran")
except GateBlocked as blocked:
    print("3. BLOCKED by the built-in floor:", blocked.result.note)

print("ledger verifies:", verify_ledger(ledger_path))
