"""Read a sealed Witness Gate ledger and report on it, in plain language.

    python -m soul_cradle.ledger_report gate-ledger.jsonl
    python -m soul_cradle.ledger_report gate-ledger.jsonl --out report.md

Built for the customer or auditor who holds a ledger and holds no
Python: the tool verifies the ledger's full hash chain, prints a
one line verdict, and writes a readable Markdown report, one
section per entry with its time, operator, action, verdict,
findings, dissent, and the policy pack identity (name, version,
sha256) where the entry recorded one.

Verification is the library's own: soul_cradle.plug.verify_ledger_detailed
walks the same chain computation as verify_ledger, so this report
cannot disagree with the library about whether a ledger is intact.

Exit status: 0 when the chain is intact, 1 when it is broken,
2 when the ledger cannot be read at all. A broken ledger still
gets a report: the verdict and the break location lead it, so the
reader can see exactly where the record stops being trustworthy.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from .plug import verify_ledger_detailed


def _iso(ts) -> str:
    """Ledger timestamps are unix seconds; render them as UTC ISO."""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError, OverflowError):
        return str(ts)


def _read_for_display(ledger_path: str):
    """Parse entries for rendering only.

    Verification never happens here; this parse exists so a ledger
    with a damaged line still yields a report for its readable
    entries. Returns (entries, bad_line_index or None).
    """
    entries = []
    bad = None
    with open(ledger_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                bad = len(entries)
                break
    return entries, bad


def _findings(result: dict) -> list:
    """Flatten the panel's findings: (assessor_id, finding) pairs."""
    out = []
    for judgment in result.get("judgments", []):
        for finding in judgment.get("findings", []):
            out.append((judgment.get("assessor_id", "?"), finding))
    return out


def _dissent_lines(dissent: list) -> list:
    lines = []
    for d in dissent:
        finding = d.get("finding") or {}
        lines.append(
            f"{d.get('flagged_by')} flagged {finding.get('check_id')} "
            f"(severity {finding.get('severity')}, "
            f"observed {finding.get('observed')!r})")
    return lines


def render_report(ledger_path: str, entries: list, detail: dict,
                  bad_line: int = None) -> str:
    lines = ["# Witness Gate Ledger Report", ""]
    lines.append(f"- Ledger file: {ledger_path}")
    lines.append(f"- Entries: {detail['entries']}")
    if detail["ok"]:
        lines.append(
            "- Verification: INTACT. The hash chain verifies end to "
            "end; no entry was altered after it was sealed.")
    else:
        lines.append(
            f"- Verification: BROKEN at entry {detail['break_index']}: "
            f"{detail['reason']}. Entries before the break verify; "
            "entries from the break onward cannot be trusted.")
    lines.append("")
    lines.append("## Entries")
    for i, entry in enumerate(entries):
        result = entry.get("result") or {}
        lines.append("")
        lines.append(f"### Entry {i}")
        lines.append(f"- Time (UTC): {_iso(entry.get('ts'))}")
        lines.append(f"- Operator: {entry.get('operator')}")
        lines.append(f"- Action: {entry.get('action')}")
        lines.append(f"- Verdict: {result.get('verdict')}")
        if result.get("note"):
            lines.append(f"- Note: {result['note']}")
        policy = entry.get("policy")
        if policy:
            lines.append(
                f"- Policy pack: {policy.get('pack')}, "
                f"version {policy.get('version')}, "
                f"sha256 {policy.get('sha256')}")
        else:
            lines.append("- Policy pack: none recorded")
        findings = _findings(result)
        if findings:
            lines.append("- Findings:")
            for assessor_id, finding in findings:
                lines.append(
                    f"  - {assessor_id}: {finding.get('check_id')} "
                    f"(severity {finding.get('severity')}, "
                    f"observed {finding.get('observed')!r})")
        else:
            lines.append("- Findings: none")
        dissent = result.get("dissent") or []
        if dissent:
            lines.append("- Dissent:")
            for text in _dissent_lines(dissent):
                lines.append(f"  - {text}")
        else:
            lines.append("- Dissent: none")
        prev = entry.get("prev_hash") or ""
        lines.append(f"- Previous hash: {prev if prev else '(genesis)'}")
        lines.append(f"- Entry hash: {entry.get('hash')}")
        if detail["break_index"] is not None and i == detail["break_index"]:
            lines.append(
                "- CHAIN BREAK: this is the first entry that fails "
                f"verification ({detail['reason']}).")
    if bad_line is not None and detail["break_index"] == bad_line:
        lines.append("")
        lines.append(
            f"Entry {bad_line} could not be read: its line is not "
            "valid JSON, so no further entries are shown.")
    lines.append("")
    return "\n".join(lines)


def build_report(ledger_path: str):
    """Verify, then render. Returns (report_text, detail_dict)."""
    detail = verify_ledger_detailed(ledger_path)
    entries, bad_line = _read_for_display(ledger_path)
    return render_report(ledger_path, entries, detail, bad_line), detail


def verdict_line(detail: dict) -> str:
    if detail["ok"]:
        return (f"VERDICT: INTACT. {detail['entries']} entries "
                "verified; the hash chain is unbroken.")
    return (f"VERDICT: BROKEN at entry {detail['break_index']}: "
            f"{detail['reason']}.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ledger_report")
    parser.add_argument("ledger")
    parser.add_argument("--out",
                        help="write the Markdown report to this file "
                             "instead of standard output")
    args = parser.parse_args(argv)
    try:
        report, detail = build_report(args.ledger)
    except OSError as exc:
        print(f"cannot read ledger: {exc}", file=sys.stderr)
        return 2
    print(verdict_line(detail))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"Report written to {args.out}")
    else:
        print()
        sys.stdout.write(report)
    return 0 if detail["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
