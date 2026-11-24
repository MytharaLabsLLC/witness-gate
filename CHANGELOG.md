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

## 2026.1 (unreleased)

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
