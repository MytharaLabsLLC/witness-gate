"""Anchor the sealed ledger's chain head outside the ledger.

The ledger's hash chain (soul_cradle.plug) catches edits to entries: a
changed line breaks every hash after it. What the chain alone cannot
catch is a full rewrite. Anyone with write access to the ledger file
could regenerate the entire chain from scratch, altered history and
all, and the new chain would verify as internally consistent, because
verification only asks whether the file agrees with itself.

An anchor closes that gap. An anchor is a small signed record of the
ledger's state at one moment: how many entries, and the hash of the
last one. Anchors live in their own file (<ledger>.anchors.jsonl),
chained to each other and signed with an operator key (HMAC-SHA256)
that never lives in the ledger. A rewritten ledger produces a head
hash that matches no signed anchor, and forging an anchor requires
the key. Keep the key somewhere the ledger writer cannot reach: a
different machine, a password manager, offline storage. For the
strongest form, also pin the latest anchor hash somewhere public or
third-party (a git commit, a timestamp service, an email to yourself):
then even the anchors file cannot be quietly replaced.

The honest limits, stated plainly:

  1. Anchoring is periodic. Entries written after the last anchor are
     covered by the chain alone until the next anchor. Anchor on a
     schedule that matches how much tail you can accept.
  2. An anchor proves the ledger at its entry count is the ledger the
     key holder saw. It does not prove the entries are true. That is
     the same contract as the chain itself: unaltered, not true.
  3. If the key is lost, no new anchors can be made and old ones
     cannot be verified. If the key leaks, anchors stop meaning
     anything. The key is the root of trust; guard it like one.

CLI:

    witness-gate-anchor init-key --key-file anchor.key
    witness-gate-anchor create gate-ledger.jsonl --key-file anchor.key
    witness-gate-anchor verify gate-ledger.jsonl --key-file anchor.key
    witness-gate-anchor show gate-ledger.jsonl

The key may also come from the environment: WITNESS_GATE_ANCHOR_KEY
(hex) or WITNESS_GATE_ANCHOR_KEY_FILE (path). Nothing is transmitted
anywhere; this module reads and writes local files only.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .plug import verify_ledger
from .review import read_ledger

ANCHOR_VERSION = "1"
KEY_ENV = "WITNESS_GATE_ANCHOR_KEY"
KEY_FILE_ENV = "WITNESS_GATE_ANCHOR_KEY_FILE"


class AnchorError(ValueError):
    """An anchor operation that must not proceed."""


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, default=str).encode()


# ---------------------------------------------------------------------------
# The key
# ---------------------------------------------------------------------------

def generate_key() -> str:
    """A fresh anchor key as hex. 32 bytes of operating-system randomness."""
    return secrets.token_hex(32)


def _decode_key(text: str) -> bytes:
    text = text.strip()
    try:
        key = bytes.fromhex(text)
    except ValueError:
        key = text.encode("utf-8")
    if len(key) < 16:
        raise AnchorError("anchor key is too short (need at least 16 bytes)")
    return key


def load_key(key_file: Optional[str] = None) -> bytes:
    """Load the anchor key from a file or the environment.

    Order: the explicit key_file, then $WITNESS_GATE_ANCHOR_KEY_FILE,
    then $WITNESS_GATE_ANCHOR_KEY. The key is never logged or printed.
    """
    path = key_file or os.environ.get(KEY_FILE_ENV)
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            return _decode_key(fh.read())
    raw = os.environ.get(KEY_ENV)
    if raw:
        return _decode_key(raw)
    raise AnchorError(
        "no anchor key: pass --key-file or set "
        f"${KEY_FILE_ENV} / ${KEY_ENV}")


# ---------------------------------------------------------------------------
# Anchor records
# ---------------------------------------------------------------------------

def anchors_path_for(ledger_path: str) -> str:
    return ledger_path + ".anchors.jsonl"


def read_anchors(anchors_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(anchors_path):
        return []
    return read_ledger(anchors_path)


def _sign(record: Dict[str, Any], key: bytes) -> str:
    return hmac.new(key, record["anchor_hash"].encode(),
                    hashlib.sha256).hexdigest()


def _seal_anchor(body: Dict[str, Any], key: bytes) -> Dict[str, Any]:
    record = dict(body)
    record["anchor_hash"] = hashlib.sha256(
        body["prev_anchor"].encode() + _canonical(body)).hexdigest()
    record["signature"] = _sign(record, key)
    return record


def _check_anchor_chain(anchors: List[Dict[str, Any]],
                        key: Optional[bytes]) -> List[str]:
    """Failures in the anchors file itself: links, hashes, signatures."""
    failures: List[str] = []
    prev = ""
    for i, a in enumerate(anchors):
        if a.get("prev_anchor") != prev:
            failures.append(f"anchor {i}: prev_anchor link broken")
            continue
        body = {k: v for k, v in a.items()
                if k not in ("anchor_hash", "signature")}
        expect = hashlib.sha256(prev.encode() + _canonical(body)).hexdigest()
        if a.get("anchor_hash") != expect:
            failures.append(f"anchor {i}: anchor_hash mismatch, tampered")
            continue
        if key is not None and not hmac.compare_digest(
                a.get("signature", ""), _sign(a, key)):
            failures.append(
                f"anchor {i}: signature mismatch, forged or wrong key")
        prev = a["anchor_hash"]
    return failures


# ---------------------------------------------------------------------------
# Create and verify
# ---------------------------------------------------------------------------

def create_anchor(ledger_path: str, key: bytes,
                  anchors_path: Optional[str] = None) -> Dict[str, Any]:
    """Pin the ledger's current head in a new signed anchor.

    Refuses, loudly, in three cases: the ledger's own chain does not
    verify (never anchor a broken record), the existing anchors do not
    verify under this key (never extend a chain you cannot vouch for),
    or the ledger is empty (nothing to pin).
    """
    apath = anchors_path or anchors_path_for(ledger_path)
    if not verify_ledger(ledger_path):
        raise AnchorError(
            "ledger chain does not verify; refusing to anchor a "
            "tampered record")
    entries = read_ledger(ledger_path)
    if not entries:
        raise AnchorError("ledger is empty; nothing to anchor")
    anchors = read_anchors(apath)
    failures = _check_anchor_chain(anchors, key)
    if failures:
        raise AnchorError(
            "existing anchors do not verify under this key: "
            + "; ".join(failures))
    body = {
        "version": ANCHOR_VERSION,
        "ledger": os.path.basename(ledger_path),
        "entries": len(entries),
        "head": entries[-1]["hash"],
        "ts": int(time.time()),
        "prev_anchor": anchors[-1]["anchor_hash"] if anchors else "",
    }
    record = _seal_anchor(body, key)
    with open(apath, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    return record


def verify_anchors(ledger_path: str, key: bytes,
                   anchors_path: Optional[str] = None
                   ) -> Tuple[bool, Dict[str, Any]]:
    """Verify the anchors and the ledger against each other.

    ok means: every anchor's link, hash, and signature check out; the
    ledger's own chain verifies; and at every anchored entry count,
    the ledger's entry hash equals the head the anchor signed. Entries
    past the last anchor are reported as the unanchored tail, not a
    failure: anchoring is periodic by design.
    """
    apath = anchors_path or anchors_path_for(ledger_path)
    details: Dict[str, Any] = {"anchors": 0, "failures": []}
    anchors = read_anchors(apath)
    if not anchors:
        details["failures"].append("no anchors found")
        return False, details
    details["anchors"] = len(anchors)
    details["failures"].extend(_check_anchor_chain(anchors, key))

    if not os.path.exists(ledger_path):
        details["failures"].append("ledger file missing")
        return False, details
    if not verify_ledger(ledger_path):
        details["failures"].append("ledger chain does not verify")
        return False, details
    entries = read_ledger(ledger_path)
    details["ledger_entries"] = len(entries)
    for i, a in enumerate(anchors):
        n = a.get("entries", 0)
        if n > len(entries):
            details["failures"].append(
                f"anchor {i}: ledger has {len(entries)} entries, "
                f"anchor claims {n}; the ledger was truncated")
        elif entries[n - 1]["hash"] != a.get("head"):
            details["failures"].append(
                f"anchor {i}: ledger head at entry {n} does not match "
                "the signed anchor; the ledger was rewritten")
    last = anchors[-1]
    details["anchored_entries"] = last.get("entries", 0)
    details["unanchored_tail"] = max(
        0, len(entries) - details["anchored_entries"])
    details["head"] = last.get("head", "")
    details["anchor_hash"] = last.get("anchor_hash", "")
    details["ok"] = not details["failures"]
    return details["ok"], details


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="witness-gate-anchor",
        description="Anchor the Witness Gate ledger's chain head with "
                    "a signed record kept outside the ledger.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-key", help="generate a new anchor key file")
    p_init.add_argument("--key-file", required=True)

    p_create = sub.add_parser("create", help="anchor the ledger's current head")
    p_create.add_argument("ledger")
    p_create.add_argument("--key-file")
    p_create.add_argument("--anchors")

    p_verify = sub.add_parser("verify", help="verify anchors against the ledger")
    p_verify.add_argument("ledger")
    p_verify.add_argument("--key-file")
    p_verify.add_argument("--anchors")

    p_show = sub.add_parser("show", help="print the latest anchor hash "
                                         "(pin this outside your building)")
    p_show.add_argument("ledger")
    p_show.add_argument("--anchors")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "init-key":
            if os.path.exists(args.key_file):
                print(f"refusing to overwrite existing key file: "
                      f"{args.key_file}", file=sys.stderr)
                return 2
            fd = os.open(args.key_file,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(generate_key() + "\n")
            print(f"anchor key written to {args.key_file} (mode 600). "
                  "Keep it apart from the ledger; losing it ends "
                  "anchoring, leaking it ends its meaning.")
            return 0

        if args.cmd == "create":
            record = create_anchor(args.ledger, load_key(args.key_file),
                                   args.anchors)
            print(f"anchored {record['entries']} entries, "
                  f"head {record['head'][:16]}...")
            print(f"anchor hash: {record['anchor_hash']}")
            print("pin that hash somewhere the ledger writer cannot "
                  "reach for the strongest form.")
            return 0

        if args.cmd == "verify":
            ok, details = verify_anchors(args.ledger,
                                         load_key(args.key_file),
                                         args.anchors)
            for failure in details["failures"]:
                print(f"FAIL: {failure}")
            if ok:
                print(f"anchors verify: {details['anchors']} anchor(s), "
                      f"{details['anchored_entries']} of "
                      f"{details['ledger_entries']} entries anchored, "
                      f"unanchored tail {details['unanchored_tail']}")
            return 0 if ok else 1

        if args.cmd == "show":
            apath = args.anchors or anchors_path_for(args.ledger)
            anchors = read_anchors(apath)
            if not anchors:
                print("no anchors yet", file=sys.stderr)
                return 2
            failures = _check_anchor_chain(anchors, None)
            if failures:
                for failure in failures:
                    print(f"FAIL: {failure}")
                return 1
            last = anchors[-1]
            print(f"entries: {last['entries']}")
            print(f"head: {last['head']}")
            print(f"anchor hash: {last['anchor_hash']}")
            return 0
    except (AnchorError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
