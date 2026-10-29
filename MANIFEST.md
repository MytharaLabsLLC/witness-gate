# Witness-Gate Publish Package — MANIFEST

Staged 2026-10-03 for the operator's final review. Plain files only — **not a git repo, nothing pushed, no commits created**.

Source extraction from: `~/workspace/mythara_archive_review/` (uncommitted Dr Mythara / Mythara_Archive working tree).
Dependency basis: only files required by the witness-gate's own imports
(`assessors.py` imports `standing.py`; `emotional_chain.py` imports `assessors.py`).

## Files

| File | Purpose | Scrub status |
|---|---|---|
| `soul_cradle/assessors.py` (611 lines) | The 8 evidence-fed witness assessors: versioned rubrics, `consult()`, `panel()` with dissent preservation, `verify_judgment()`, membrane hook `assessor_bounds_check()`, standing-matrix witness declarations | CLEAN — redacted: 8x rubric `source` strings "Herb's framework" → "the operator's framework"; guidance "under Herb's name" → "under the operator's name"; 3x "Escalate to Herb" → "Escalate to the operator" |
| `soul_cradle/emotional_chain.py` (469 lines) | Tamper-evident hash-chained attestation records attested by the 8 witnesses; genesis block with declared operator attestations; `verify()`, `history()`, `analyze_patterns()` (heuristic, labeled non-diagnostic) | CLEAN — redacted: docstring example `operator="herb"` → `operator="operator"`; patched absolute import `from soul_cradle.assessors` → relative `from .assessors` for standalone portability |
| `soul_cradle/standing.py` (278 lines) | Role→declaration standing matrix (wronged/witness/trespasser/stranger); HMAC-SHA256-signed `Declaration`s via `StandingAuthority`; signing key from `STANDING_KEY` env or ephemeral dev key with a loud warning (not production posture) | CLEAN — no secrets found; key handling is env/ephemeral by design; no personal data |
| `soul_cradle/__init__.py` | Minimal package init written for this package — exports only the three modules, `__version__ = "2026.1"` | NEW — deliberately does NOT import the full Soul Cradle stack (forge, will, authorization, identity, pantheon were left out as out of scope) |
| `tests/test_assessors.py` (206 lines → minus 1 test) | 47-test suite for assessors + standing | ADJUSTED — removed `test_legacy_bot_shims_delegate_to_core` (imports legacy god-bot shims `demeter_bot`/`nemesis_bot` from the full archive tree, intentionally excluded from this extract); documented here. All 47 remaining tests pass. |
| `tests/test_emotional_chain.py` (149 lines) | Tests for the chain: genesis, recording, seals, verification | CLEAN — copied verbatim, no secrets or personal data found |
| `README.md` | Package framing: what it is, honest contract, what it is NOT (never "emotion AI"), quick start, provenance | NEW |
| `LICENSE-NOTE.md` | License comparison + recommendation vs the Nov 2026 defensive-publication/patent fork | NEW — not a license; no legal advice |
| `PUBLISH-CHECKLIST.md` | What the operator must decide/approve before publish | NEW |

## Secret/personal-data sweep

Grep patterns over every staged code file: `sk_`, `api_key`/`API_KEY`, `token`/`TOKEN` (matches were only stdlib `secrets.token_bytes/hex` — crypto RNG, not stored secrets), `password`/`PASSWORD`, email addresses, personal names (Herb, Amir), phone numbers, URLs with credentials, `mailto:`.

- **No API keys, tokens, passwords, emails, phone numbers, or credential URLs found.**
- Personal name redacted: "Herb" → "the operator" (12 occurrences across assessors.py + emotional_chain.py docstring).
- No custody/Hague/personal material touched — `assessment_custody_injustice.py` never opened, never copied.

## Verification run

- `python3 -m pytest tests/` → **47 passed** (2026-10-03)
- Smoke test: genesis + record + `verify()` → ok; `panel()` → verdict path works; package imports with only the stdlib on path.

## Deliberately excluded

- The rest of `soul_cradle/` (forge.py, will.py, authorization.py, identity.py, pantheon.py, bot_witness.py, benevolence.py, health.py) — out of scope for the trust-layer extract.
- Legacy god-bot shims (`*_bot.py`, e.g. demeter_bot.py) — legacy compatibility wrappers, not the witness gate.
- `divine_implementations/emotional_blockchain.py`, `demo_emotional_blockchain.py`, `.hephaestus_forge/` — older experimental chain drafts, superseded by the 2026.1 rebuild.
- All git state, audit jsonl logs, `__pycache__`.
