# Witness Gate: Diligence Summary

This document is the short factual record an evaluator needs: what
the Witness Gate is, how it is built, what has been measured, and
where its limits are stated. It describes release 2026.4
(2026-11-26). Security reporting is covered in SECURITY.md.

## What it is

The Witness Gate is a Python library that sits between an AI
agent's proposed action and the action itself. Before the action
runs, the gate judges it against observable evidence. The verdict
is enforced by the gate, not advised by it: a blocked action never
runs, and no caller, framework, or callback can override a block.
Every judgment is sealed in a hash-chained ledger that stays on
the operator's own machine.

The gate is extracted from SoulCradle, the governed deployment
sold by Mythara Labs LLC (Denver, Colorado). The Gate itself is
free and Apache-2.0 licensed, with no paid tier and no hosted
version.

It is not emotion AI. It does not detect, infer, or verify
emotions or inner states. Under EU AI Act framing, it attests
self-reported records: it witnesses what was declared, checks the
action against evidence-fed rubrics, and preserves disagreement
for human review.

## Architecture in brief

- **Eight witness assessors** (`soul_cradle/assessors.py`). Each is
  a versioned rubric over observable evidence about a proposed
  action. An assessor reads only the evidence keys its rubric
  declares, abstains when its domain is not engaged, and flags
  with the evidence cited when a check fails. Once an assessor is
  engaged, missing evidence is itself a finding, never a pass
  (fail-closed). A packet that engages no assessor is cleared by
  universal abstention.
- **The panel.** The eight judgments combine into one verdict:
  `clear`, `flagged`, `contested`, or `blocked`. A
  critical-severity finding blocks. Where assessors disagree, the
  dissent is preserved in the record, never averaged away.
- **The Gate wrapper** (`soul_cradle/plug.py`). Decorate a
  function and every call is judged first, then run, held for a
  human decision, or refused, according to the verdict.
- **Callers beyond Python.** An HTTP service (`POST /assess`,
  `GET /health`, `GET /rubrics`), an MCP server with four tools,
  framework adapters for LangGraph, CrewAI, and the OpenAI Agents
  SDK shape, and worked clients for curl, JavaScript/TypeScript,
  and Go.
- **Human review.** Held judgments surface in terminal and web
  review consoles. Human decisions are sealed in a second
  hash-chained ledger; the judgment ledger is never edited, and a
  blocked judgment can be acknowledged but never approved into a
  pass.
- **Standard library only.** The package has zero third-party
  dependencies and makes no network calls of its own. The optional
  HTTP service and web console bind to 127.0.0.1 by default and
  carry no authentication of their own (see SECURITY.md).

## Measured results

All numbers below are reproducible with scripts in this
repository.

- **Test suite:** 108 tests, all passing, run in CI on Python
  3.10, 3.11, and 3.12 (`pytest tests/`).
- **Red team:** `evals/red_team.py` runs 12 adversarial evidence
  packets, each built from a favorable baseline with one thing
  broken (deception, disproportionate harm, no consent, no
  disclosure, irreversibility at high variance, hidden costs, and
  others). Result: 12 of 12 behaved as required, zero escapes.
  Both critical packets were blocked, every other broken packet
  was held, and the baseline cleared.
- **Latency:** measured 2026-11-26 with `benchmarks/latency.py`.
  Panel judgment: mean 0.19 ms, p95 0.20 ms. A sealed gate check
  (judgment plus ledger write): mean 0.292 ms. Sub-millisecond on
  the machine measured; exact decimals move with machine load.

## Policy packs (bring your own law)

Release 2026.4 adds customer policy packs (`soul_cradle/policy.py`).
A pack is a JSON file with a name, a version, and rules. Each rule
names one of the eight witnesses as its assessor, one evidence
key, one operator (`equals`, `not_equals`, `in`, `not_in`,
`exists`, `missing`, `gt`, `gte`, `lt`, `lte`, `contains`), a
severity (`low`, `medium`, `high`, `critical`), and a
plain-language finding. When a rule's condition matches the
evidence, its witness raises a finding marked
`policy:<pack>:<rule id>`, and the finding flows through the panel
exactly like a built-in one.

Three properties hold by construction:

- **Packs only add findings.** A pack can never suppress, clear,
  or downgrade a built-in finding, and there is no pack syntax
  for removing a built-in check. The three built-in criticals
  (eros.deception, hermes.deception, nemesis.disproportion) block
  regardless of any pack. A pack can tighten; it can never loosen.
- **Loading fails closed.** Strict validation rejects malformed
  JSON, an unknown assessor or operator, a bad severity, a
  duplicate rule id, or a misused value, raising `PolicyError`
  with a plain message. A Gate configured with a pack that cannot
  load refuses to be constructed rather than judge bare.
- **Every judgment names its law.** Each ledger entry sealed by a
  gate carrying a pack records the pack's name, version, and the
  sha256 of its canonical form, so a judgment can later be tied
  to the exact rules applied to it.

A worked example ships in `examples/customer-policy.json` with
`examples/policy_quickstart.py`. Starter templates mapped to the
NIST AI Risk Management Framework and to EU AI Act obligations
ship as `examples/policy-nist-ai-rmf.json` and
`examples/policy-eu-ai-act.json`; both are labeled in their own
findings as starter templates, not legal advice.

## Ledger properties

- **Hash-chained and tamper-evident.** Judgments are appended to
  a JSONL ledger in which each entry chains to the one before it.
  `verify_ledger()` proves the file unaltered.
- **Anchoring.** Because a full rewrite of the file would
  regenerate a self-consistent chain, the ledger can be anchored:
  a small signed record (entry count and head hash, HMAC-SHA256)
  kept in a separate file under an operator key that never lives
  in the ledger. A rewritten ledger matches no signed anchor.
- **Export.** The ledger exports to JSON, CSV, or
  OpenTelemetry-style log records for a logging or SIEM stack.
  The chain is verified before anything is exported; a tampered
  ledger exports nothing.
- **The honest limit.** The chain and the anchors prove a record
  unaltered. They do not prove a record true. `verified` on a
  record means exactly this: every engaged witness cleared the
  attestation on the evidence given, nothing more.

## Versioning

Releases are calendar-versioned (`YYYY.N`) and recorded in
CHANGELOG.md. The package version and the rubric version are
separate numbers: features can land without the judging rules
changing, and any release that changes verdict behavior says so
in its changelog entry, in plain words, first. Only the latest
release receives fixes (see SECURITY.md).

## License

Apache-2.0. See LICENSE.
