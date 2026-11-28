# SoulCradle Support Terms

**DRAFT. This document is a draft prepared for Herb Velez's
approval. It is not published, not in force, and not an offer.
Nothing in it binds Mythara Labs LLC until it is approved and
issued to a customer in writing.**

## Scope

These draft terms describe the support that would accompany the
commercial SoulCradle tiers sold by Mythara Labs LLC:

| Tier | Price |
| --- | --- |
| Self-Guided Pilot | $5,000 |
| Commercial | $24,000 per year |
| Enterprise | from $75,000 per year |

The Witness Gate is free and Apache-2.0 licensed. It has no paid
tier and no support commitment; questions about the Gate are
handled on a best-effort basis and are not covered by these terms.

## Contact channel

Support is by email: MytharaLabsLLC@yahoo.com. A support request
should name the deployment, the release version in use (see
CHANGELOG.md), and the behavior observed. Security reports go to
the same address and follow SECURITY.md: please do not open a
public issue for a vulnerability.

## Response-time targets

Targets below are first-response targets on business days
(Monday to Friday, excluding U.S. federal holidays), measured
from receipt of the email. They are targets, not guarantees, in
this draft.

| Tier | First response target |
| --- | --- |
| Self-Guided Pilot | within 5 business days |
| Commercial | within 2 business days |
| Enterprise | within 1 business day |

Security mail is answered within 5 business days at every tier,
per SECURITY.md. A first response acknowledges the report and
states the next step; it is not a promise of a fix date.

## Updates and release cadence

- **Versioned releases.** SoulCradle and the Witness Gate are
  released in calendar versions (`YYYY.N`), and every release is
  recorded in CHANGELOG.md.
- **Verdict changes are called out.** The package version and the
  rubric version are separate numbers. Any release that changes
  verdict behavior says so in its changelog entry, in plain
  words, first, so a customer can decide when to upgrade.
- **Security patch policy.** Only the latest calendar release
  receives fixes (per SECURITY.md). A security fix ships as a new
  versioned release with a changelog entry; customers are expected
  to move to it.
- **Standing commitment.** Releases continue on a regular cadence
  so the rubrics and the pack validation stay current to threat
  standards. Customers keep their own ledgers and anchors across
  upgrades; ledgers written by earlier releases verify unchanged.

## What support covers

- Questions about installing, configuring, and operating the
  software at the licensed tier.
- Help reading verdicts, ledger verification results, and anchor
  verification results.
- Diagnosis of defects in the shipped, unmodified software, and
  workarounds where they exist.
- Guidance on writing and validating customer policy packs,
  including why a pack failed to load.

## What support does not cover

- **Legal or compliance advice.** Policy packs, including the
  starter templates in `examples/`, are configuration, not legal
  advice. Whether a deployment satisfies a law or a framework is
  the customer's determination, with their own counsel.
- **Changing the floor.** Support will not help suppress, clear,
  or downgrade a built-in finding. The three built-in criticals
  block regardless of configuration; that is a property of the
  product, not a defect.
- **Custom development.** New features, new assessors, and
  integrations with a customer's own systems are not support.
  They may be quoted separately.
- **Modified or old releases.** Support applies to the latest
  release, unmodified. Defects that arise from local changes to
  the source are the customer's to diagnose.
- **Customer infrastructure.** Hosting, proxies, key custody for
  anchor keys, backups, and the customer's own logging or SIEM
  stack are operated by the customer. Anchoring only proves what
  it can prove if the anchor key is kept apart from the ledger,
  as documented.
- **On-site services and training**, unless separately agreed in
  writing.
- **Recovery of unanchored, unbacked-up records.** The hash chain
  proves a ledger unaltered; it cannot reconstruct one that was
  deleted and never backed up or anchored.
