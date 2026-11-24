# Witness Gate

[![tests](https://github.com/MytharaLabsLLC/witness-gate/actions/workflows/tests.yml/badge.svg)](https://github.com/MytharaLabsLLC/witness-gate/actions/workflows/tests.yml)

Your agent is about to send, pay, delete, or publish. This gate judges
the action first, against evidence, and seals the verdict in a
hash-chained record that never leaves your building. A block cannot be
overridden by the caller, the framework, or a callback.

**Measured, not promised:** 74 tests passing, in CI on Python 3.10,
3.11, and 3.12 · a 12-packet adversarial battery with zero escapes ·
sub-millisecond judgments (see *Proof, measured*) · zero dependencies ·
Apache-2.0.

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

```bash
pip install git+https://github.com/MytharaLabsLLC/witness-gate
```

```python
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
```

Three steps: create a Gate, decorate the actions that matter, call them.
The wrapper builds the evidence packet from the call's own arguments,
calls the panel, enforces the verdict, and seals every judgment in a
hash-chained ledger (`verify_ledger()` proves it unaltered):

- `clear` — the action runs.
- `flagged` / `contested` — the action does not run; `HeldForReview` is
  raised unless an `on_hold` callback (the human decision point) returns
  an explicit True.
- `blocked` — the action never runs; `GateBlocked` is raised and no
  callback can override a critical witness.

## The judgment core, directly

The wrapper sits on `panel()`, which you can also call yourself:

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

Tests: `pytest tests/` (zero dependencies).

## The SDK

The gate ships as an installable Python SDK, standard library only:

```bash
pip install git+https://github.com/MytharaLabsLLC/witness-gate
```

That installs the `soul_cradle` package (the Gate, the panel, the
ledger tools) plus five commands: `witness-gate` (the HTTP service),
`witness-gate-mcp` (the MCP server), `witness-gate-review` and
`witness-gate-review-web` (the review consoles), and
`witness-gate-export` (the ledger exporter). `examples/quickstart.py`
is the whole SDK in one file: decorate, call, done. A separate Gate
instance per agent gives each agent its own operator name, ledger,
and default evidence; that is the per-agent policy surface.

## Call it from any stack

Python is one caller among many. Run the gate once inside your own
environment and every stack can reach it:

```bash
witness-gate --port 8765 --ledger gate-ledger.jsonl
```

`POST /assess` with `{"action": "...", "evidence": {...}}` returns
the verdict JSON; `GET /health` and `GET /rubrics` round out the
surface. Agent frameworks that speak the Model Context Protocol skip
HTTP entirely: point the framework at `witness-gate-mcp` and the
agent gets four tools: `witness_gate_assess`,
`witness_gate_verify_ledger`, `witness_gate_review_queue`, and
`witness_gate_rubrics`. Worked clients for curl, JavaScript/
TypeScript, and Go live in `examples/clients.md`.

## Framework adapters

For the three frameworks agent builders reach for first,
`soul_cradle.adapters` provides the native shape with no added
dependency: `langgraph_node(gate)` is a LangGraph node that writes
the verdict back into state and raises on a block, `crewai_tool(gate)`
is a CrewAI tool that returns the verdict as JSON, and
`openai_function_tool(gate)` returns the OpenAI-style function
definition plus its handler, ready for the OpenAI Agents SDK.

## Evidence, derived not declared

The panel judges the evidence it is given, so `soul_cradle.evidence`
derives what can be derived: consent is looked up in an append-only
ConsentBook rather than asserted by the caller, reversibility is
derived from the action type (sending, deleting, and paying do not
undo), and affected parties are pulled from the call arguments. What
cannot be derived is still supplied by the caller, and the panel
fails closed when it is missing.

## The review console

Held judgments need a human surface. `witness-gate-review list`
shows every undecided hold in a ledger; `witness-gate-review decide`
records the human's call in a second hash-chained ledger beside the
first. The judgment record is never edited, and a blocked judgment
can be acknowledged but never approved into a pass. Reviewers who
should not need a shell get the same queue in a browser:
`witness-gate-review-web --ledger gate-ledger.jsonl` serves a local
console on 127.0.0.1:8766 with the same rules and the same sealed
decisions. It is a local operations tool with no authentication of
its own; run it on the machine that holds the ledger, or behind your
own authenticated proxy.

## Export

`witness-gate-export <ledger> --format json|csv|otlp` turns the
sealed ledger into the formats a logging or SIEM stack already eats,
including OpenTelemetry-style log records. The chain is verified
before anything is exported; a tampered ledger exports nothing.

## Proof, measured

Reproduce both numbers with the scripts in this repo:

* Latency (`benchmarks/latency.py`, 200 panel calls, measured
  2026-11-23 on a shared cloud VM): mean 0.24 to 0.28 ms, median
  0.23 ms, p95 0.28 to 0.47 ms per judgment across repeated runs.
  Sub-millisecond on every run; the exact decimals move with
  machine load, so they are stated as a range.
* Red team (`evals/red_team.py`): 12 adversarial packets built from a
  favorable baseline with one thing broken each (deception,
  disproportionate harm, no consent, no disclosure, irreversible at
  high variance, hidden costs, and more). Both critical packets were
  blocked, every other broken packet was held, the baseline cleared:
  12 of 12 behaved as required, zero escapes.
* Test suite: 74 tests, all passing.

## Cost and versioning

The Witness Gate is free, Apache-2.0, and stays that way: there is
no paid tier of the Gate, no per-action pricing, and no hosted
version, by design. Mythara Labs sells SoulCradle, the full governed
deployment this Gate is extracted from, with email support answered
within 5 business days. The Gate is the open front door.

Releases are calendar-versioned (`YYYY.N`) and recorded in
`CHANGELOG.md`. The package version and the rubric version are
separate numbers on purpose: features can land without the judging
rules changing, and any release that changes verdict behavior says
so in its changelog entry, in plain words, first.

## Design provenance

Extracted from the Mythara Soul Cradle framework (Mythara Labs LLC, Denver, Colorado). The rubrics are the operator's internal framework, labeled honestly as such — not an external standard. Rubric versioning (`YYYY.N` + effective date) keeps old judgments interpretable after rubric updates.
