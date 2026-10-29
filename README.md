# Witness Gate

An accountable-AI trust layer: **eight fail-closed evidence-fed witness assessors**, **tamper-evident hash-chained attestation records**, and a **preserved dissent panel**. Self-contained Python, standard library only.

## What it is

A gate that sits between an AI agent's proposed action and the action itself:

1. **Eight witnesses** (`soul_cradle/assessors.py`) — each a versioned rubric over *observable evidence* about a proposed action. Each assessor reads only the evidence keys its rubric declares, **abstains when its domain is not engaged** (humility, not guessing), **flags with the evidence cited** when a check fails or evidence is missing (fail-closed), and **seals every judgment with a content hash**.
2. **The emotional chain** (`soul_cradle/emotional_chain.py`) — a tamper-evident chain of witness-attested records. Every entry carries the witnesses' sealed judgments chained alongside it. Disagreement is **preserved, never averaged away**.
3. **The standing matrix** (`soul_cradle/standing.py`) — structural law for who may declare what: the wronged declares trespass, a witness declares only what it observed, a stranger declares nothing. Declarations are HMAC-signed, timestamped, and auditable.

The panel's verdicts: `clear` (every engaged assessor cleared), `flagged` (engaged assessors flagged, none cleared — no dissent), `contested` (some flagged, some cleared — **dissent is the signal**), `blocked` (a critical-severity finding — the action is refused, no outvoting).

## The honest contract

- The chain proves a record is **unaltered**. It does not prove the record is **true**. Tamper-evidence is not truth.
- The witnesses attest what they **observed in the report and the evidence given**. They never claim to verify what anyone felt. A person's inner state remains their own; no system verifies it.
- `verified` on a record means exactly this: every engaged witness cleared the attestation on the evidence given — nothing more.

## What it is NOT

This is **not** "emotion AI." It does not detect, infer, or verify emotions or inner states. Under EU AI Act framing, it attests **self-reported records** — the system witnesses what was declared, checks the *action of recording it* against evidence-fed rubrics, and preserves the disagreement for human review. Never marketed as emotion detection.

## Quick start

```python
from soul_cradle.assessors import panel
from soul_cradle.emotional_chain import EmotionalChain

evidence = {
    "principal_consent": True,
    "fully_disclosed": True,
    "reversible": True,
    "deception_involved": False,
    # ... see the evidence schema in soul_cradle/assessors.py docstring
}
result = panel("Send the weekly report", evidence)
print(result.verdict)   # clear | flagged | contested | blocked

chain = EmotionalChain(operator="operator")
rec = chain.record(subject_id="user-1", emotion="content", intensity=0.4,
                   context="The report as the subject stated it.",
                   reporter_id="user-1")
ok, details = chain.verify()
```

Tests: `pytest tests/` (47 tests, zero dependencies).

## Design provenance

Extracted from the Mythara Soul Cradle framework (Mythara Labs LLC, Denver, Colorado). The rubrics are the operator's internal framework, labeled honestly as such — not an external standard. Rubric versioning (`YYYY.N` + effective date) keeps old judgments interpretable after rubric updates.
