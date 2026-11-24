"""The human surface: a review console for held judgments.

When the gate holds an action (flagged or contested) or refuses it
(blocked), a person has to be able to see it and decide. This module is
that surface, terminal-grade:

    witness-gate-review list   --ledger gate-ledger.jsonl
    witness-gate-review decide --ledger gate-ledger.jsonl \
        --entry <entry-hash> --decision approved --by dana

Decisions are appended to a decisions ledger beside the judgment
ledger (<ledger>.decisions.jsonl), hash-chained the same way, each one
naming the judgment entry it answers. The judgment ledger itself is
never edited: the record of what the panel said stays sealed, and the
record of what the human decided is sealed next to it.

A blocked judgment can be viewed and its decision recorded as
acknowledged, but no decision in this console turns a block into a
pass; enforcement code must refuse blocked actions outright.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time

from .plug import verify_ledger

HELD = ("flagged", "contested", "blocked")


def decisions_path(ledger_path: str) -> str:
    return ledger_path + ".decisions.jsonl"


def read_ledger(ledger_path: str) -> list[dict]:
    entries = []
    with open(ledger_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def holds(ledger_path: str) -> list[dict]:
    """Judgment entries a human still needs to see."""
    decided = set()
    dpath = decisions_path(ledger_path)
    if os.path.exists(dpath):
        for entry in read_ledger(dpath):
            decided.add(entry.get("entry_hash"))
    return [e for e in read_ledger(ledger_path)
            if e.get("result", {}).get("verdict") in HELD
            and e.get("hash") not in decided]


def decide(ledger_path: str, entry_hash: str, decision: str,
           reviewer: str) -> dict:
    if decision not in ("approved", "rejected", "acknowledged"):
        raise ValueError("decision must be approved, rejected, or acknowledged")
    targets = {e["hash"]: e for e in read_ledger(ledger_path)}
    if entry_hash not in targets:
        raise ValueError(f"no ledger entry with hash {entry_hash}")
    verdict = targets[entry_hash].get("result", {}).get("verdict")
    if verdict == "blocked" and decision == "approved":
        raise ValueError("a blocked judgment cannot be approved; "
                         "record it as acknowledged instead")
    dpath = decisions_path(ledger_path)
    prev = ""
    if os.path.exists(dpath):
        existing = read_ledger(dpath)
        if existing:
            prev = existing[-1]["hash"]
    body = {"entry_hash": entry_hash, "verdict": verdict,
            "decision": decision, "reviewer": reviewer,
            "at": int(time.time()), "prev_hash": prev}
    body["hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True).encode()).hexdigest()
    with open(dpath, "a") as fh:
        fh.write(json.dumps(body, sort_keys=True) + "\n")
    return body


def main(argv=None):
    parser = argparse.ArgumentParser(prog="witness-gate-review")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="show undecided holds")
    p_list.add_argument("--ledger", required=True)
    p_dec = sub.add_parser("decide", help="record a human decision")
    p_dec.add_argument("--ledger", required=True)
    p_dec.add_argument("--entry", required=True)
    p_dec.add_argument("--decision", required=True,
                       choices=["approved", "rejected", "acknowledged"])
    p_dec.add_argument("--by", required=True)
    args = parser.parse_args(argv)

    if not verify_ledger(args.ledger):
        print("ledger does not verify: the hash chain is broken")
        return 1
    if args.cmd == "list":
        pending = holds(args.ledger)
        if not pending:
            print("no undecided holds")
        for e in pending:
            r = e["result"]
            print(f"{e['hash'][:12]}  {r['verdict']:<9}  {e['action']}")
        return 0
    body = decide(args.ledger, args.entry, args.decision, args.by)
    print(f"recorded: {body['decision']} on {args.entry[:12]} "
          f"by {args.by} (decision hash {body['hash'][:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
