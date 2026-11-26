# Changelog

All notable changes to the Witness Gate SDK are recorded here.

Versioning is calendar-based: `YYYY.N`, where N is the release number
within the year. The package version and the rubric version are
separate numbers on purpose: the SDK can gain features without the
judging rules changing, and a rubric change is always called out in
its own entry, with the assessors' own version and effective date
(`soul_cradle.assessors.rubric_inventory()` reports them at runtime).
The MCP server also reports a version in its server info (0.2.0);
that number tracks the MCP tool surface only and is governed by
neither the package version nor the rubric version.
A release that changes any verdict behavior says so in its entry, in
plain words, before anything else.

## 2026.3 (2026-11-26)

Corrections only; no verdict behavior changes. The judging core, the
rubrics, and every verdict the panel can return are exactly as in
2026.2. What changed is that three places where the documentation,
and one export, disagreed with the shipped behavior now agree with
it. All three were found by a full function test of the package
against its own documentation.

- The quick-start example in README.md and in the `soul_cradle.plug`
  module docstring showed a four-key evidence packet and promised
  the decorated function would run, judged first, then run. That
  packet in fact returns `contested` and raises `HeldForReview`;
  the function never runs. The examples now pass the complete
  evidence packet, in the style of `examples/quickstart.py`, and
  run as documented.
- The claim "missing evidence fails closed" was stated without its
  condition in README.md, in the `soul_cradle.evidence` docstring,
  and in the `witness_gate_assess` MCP tool description. The shipped
  behavior, now stated everywhere the claim appears: fail-closed
  applies per assessor once the evidence engages that assessor (at
  least one of its evidence keys present), and a packet that
  engages no assessor is cleared by universal abstention.
- `soul_cradle.export.to_csv` read `assessor_id` and `verdict` keys
  that panel dissent entries do not carry, so the dissent column of
  a CSV export rendered as `None:None` for every dissenting entry.
  It now renders the dissent from the keys the panel actually
  records (`flagged_by`, the finding's `check_id`, `severity`, and
  `observed` value, `finding_count`, `cleared_by`, `abstained`),
  and the test suite asserts the dissent content of a CSV export.
- The `soul_cradle.plug` docstring named a `BlockedByGate`
  exception; the exception is `GateBlocked`. Corrected.

## 2026.2 (2026-11-25)

- Ledger anchoring (`soul_cradle.anchor`, `witness-gate-anchor`):
  the ledger's hash chain catches edits to entries, but a full
  rewrite of the file would regenerate a self-consistent chain.
  An anchor pins the ledger's entry count and head hash in a
  separate file, chained to prior anchors and signed with an
  operator key (HMAC-SHA256) kept apart from the ledger, so a
  rewritten or truncated ledger matches no signed anchor. Creating
  an anchor refuses a ledger whose chain does not verify, and
  verification reports entries past the last anchor as an
  unanchored tail rather than failing them. No verdict behavior
  changes; the judging core is untouched.

## 2026.1 (2026-11-24)

The first SDK release: the Gate as an installable, callable package.

- `Gate` plug-and-play wrapper (`soul_cradle.plug`): decorate the
  actions that matter; clear runs, flagged and contested hold for a
  human, blocked refuses with no override. Every judgment is sealed
  in a hash-chained JSONL ledger; `verify_ledger` checks the chain.
- HTTP service (`witness-gate`): `POST /assess`, `GET /health`,
  `GET /rubrics`. Any stack that can make an HTTP request can call
  the court.
- MCP server (`witness-gate-mcp`): four tools over stdio,
  `witness_gate_assess`, `witness_gate_verify_ledger`,
  `witness_gate_review_queue`, and `witness_gate_rubrics`.
- Evidence derivation (`soul_cradle.evidence`): consent is looked up
  in an append-only consent book, never taken from the caller;
  reversibility is derived from the action type.
- Review consoles: terminal (`witness-gate-review`) and web
  (`witness-gate-review-web`). Decisions are sealed in a second
  hash-chained ledger; the judgment ledger is never edited, and a
  blocked judgment can be acknowledged but never approved.
- Export (`witness-gate-export`): the sealed ledger to JSON, CSV, or
  OpenTelemetry-style log records. A ledger whose chain does not
  verify exports nothing.
- Framework adapters (`soul_cradle.adapters`): a LangGraph node, a
  CrewAI tool, and an OpenAI-style function tool, with no added
  dependencies; the package remains standard-library only.
- Proof, measured 2026-11-23 on a shared cloud VM: sub-millisecond
  judgments (mean 0.24 to 0.28 ms across repeated runs of 200
  calls); a 12-case red-team battery with zero escapes.

No verdict behavior changed in this release: the assessors and their
rubrics are the ones the repository has carried since its first
public commit.
