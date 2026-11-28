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

## 2026.5 (2026-11-27)

An addition, not a correction. Verdict behavior is unchanged: the
built-in rubrics, the panel logic, and the policy pack semantics
are exactly as they were in 2026.4. This release widens the
surfaces and the operator tooling around the same judgment.

- Policy packs now configure on both servers. `witness-gate`
  (HTTP) and `witness-gate-mcp` accept `--policy pack.json` at
  startup, or a pack as a JSON object on a single request, which
  judges that request only. `GET /policy` reports the pack a
  server carries, and every response carries the applied pack's
  name, version, and sha256. Packs are accepted as JSON objects,
  never as file paths, on both surfaces. An invalid pack fails
  closed: the server refuses to start, or the request is refused
  with nothing judged.
- New ledger reader: `witness-gate-ledger` (or
  `python -m soul_cradle.ledger_report`) verifies a sealed
  ledger's full hash chain, prints a one line verdict, and writes
  a readable Markdown report, one section per entry, naming the
  first broken entry when the chain fails. Its verification is
  the library's own chain computation, exposed as
  `verify_ledger_detailed` in `soul_cradle.plug`, so the reader
  cannot disagree with `verify_ledger`.
- Container form: a `Dockerfile` and `CONTAINER.md` ship the
  HTTP service as a container, with the plain venv equivalent
  documented alongside.
- Benchmarks: `benchmarks/scale.py` with dated results in
  `benchmarks/RESULTS-2026-11-27.md`: sustained 3,120 checks per
  second (median 0.294 ms per sealed check) and ledger growth to
  1,000,000 entries with a 69.9 second full verification,
  measured on a throttled shared VM and labeled there as a floor
  for real hardware, not a ceiling.
- Paper ring: `DILIGENCE.md` (the verified facts about the gate,
  with dates) and `SUPPORT.md` (support terms, headed as a draft
  that is not in force), plus two starter policy packs,
  `examples/policy-nist-ai-rmf.json` and
  `examples/policy-eu-ai-act.json`, each labeled a starter
  template, not legal advice.
- Tests: 121 passing, up from 108 in 2026.4 (9 new server policy
  tests, 4 new ledger reader tests).

## 2026.4 (2026-11-26)

An addition, not a correction. Verdict behavior is unchanged for
any gate that does not configure a policy pack: the built-in
rubrics, the panel logic, and every verdict of 2026.3 are exactly
as they were. For a gate that does configure a pack, verdicts can
only move in one direction, toward more findings, never fewer.

- New module `soul_cradle.policy`: customer policy packs. A pack
  is a JSON file of rules (one of the eight witnesses, one evidence
  key, one operator, one severity, one finding text) that judge
  alongside the built-in rubric as data, with no code changes.
  Operators: equals, not_equals, in, not_in, exists, missing, gt,
  gte, lt, lte, contains. Policy findings are marked in the result
  with check_id `policy:<pack>:<rule id>` and flow through the
  existing panel verdict logic.
- The floor is not negotiable, by construction: a pack can only
  add findings. It cannot suppress, clear, or downgrade a built-in
  finding, there is no pack syntax for removing a built-in check,
  and the three built-in criticals block regardless of any pack.
- Loading fails closed: strict validation (malformed JSON, unknown
  assessor or operator, bad severity, duplicate rule id, misused
  value) raises `PolicyError`, and a `Gate` configured with a pack
  that cannot load refuses to be constructed.
- `Gate` gains an optional `policy` argument (file path, dict, or
  loaded `PolicyPack`). Every entry sealed by a gate carrying a
  pack records the pack's name, version, and the sha256 of its
  canonical form, inside the sealed body. Ledgers written before
  this release verify unchanged, policy-era entries verify, and a
  chain can continue across the boundary; all three directions
  are covered by tests in `tests/test_policy.py`, including a
  fixture ledger sealed by the 2026.3 code.
- Worked example: `examples/customer-policy.json` (a fictional
  regulated shop) and `examples/policy_quickstart.py`, which runs
  a clear, a policy block, and a built-in floor block end to end.
  README gains a "Bring your own law" section.

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
