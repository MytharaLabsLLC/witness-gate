"""The whole SDK in one file: decorate, call, done."""
from soul_cradle import Gate

gate = Gate(ledger_path="gate-ledger.jsonl")


@gate.action(evidence=lambda amount: {
    "principal_consent": True, "fully_disclosed": True,
    "reversible": amount < 500, "deception_involved": False,
    "affected_parties": ["customer"], "disproportionate_harm": False,
    "contradicts_commitments": False, "sustains_long_term": True,
    "hidden_costs_addressed": True, "safe_on_repetition": True,
    "strengthens_relationship": True, "precedent_setting": False,
    "variance": "low",
})
def issue_refund(amount):
    return f"refunded {amount}"


print(issue_refund(120))  # the panel clears it, the call runs, the
                          # judgment is sealed in gate-ledger.jsonl
