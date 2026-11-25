# Security Policy

## Reporting a vulnerability

Email MytharaLabsLLC@yahoo.com with the details. Please do not open
a public issue for a vulnerability until we have had a chance to
look at it. We answer security mail within 5 business days.

## Scope notes

The Witness Gate is a local, standard-library-only Python package.
It makes no network calls of its own; the optional HTTP service and
web review console bind to 127.0.0.1 by default and carry no
authentication of their own, so run them only where that is safe or
behind your own authenticated proxy.

The ledger's hash chain and the optional signed anchoring prove a
record unaltered. They do not prove a record true, and they do not
protect a ledger whose writer and verifier are the same unchecked
party. The anchor key is the root of trust for anchoring; guard it
like one.

## Supported versions

Only the latest calendar release (see CHANGELOG.md) receives fixes.
