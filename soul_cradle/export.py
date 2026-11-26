"""Export the sealed ledger into the tools a buyer already runs.

The record stays in the customer's building; this module turns the
JSONL ledger into formats their logging and SIEM stack already eats:

    python -m soul_cradle.export gate-ledger.jsonl --format json
    python -m soul_cradle.export gate-ledger.jsonl --format csv
    python -m soul_cradle.export gate-ledger.jsonl --format otlp

Formats: json (array of entries), csv (one row per judgment, verdict
and dissent flattened), otlp (OpenTelemetry-style log records, one per
judgment, verdict and assessor carried as attributes). The chain is
verified before anything is exported; a tampered ledger exports
nothing.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys

from .plug import verify_ledger
from .review import read_ledger


def to_json(entries: list[dict]) -> str:
    return json.dumps(entries, indent=2)


def _format_dissent(dissent: list[dict]) -> str:
    """Render the panel's dissent entries from the keys they carry.

    Each entry records who flagged (flagged_by), the finding that
    led (check_id, severity, observed), how many findings that
    assessor raised (finding_count), and who cleared or abstained
    (cleared_by, abstained).
    """
    parts = []
    for d in dissent:
        finding = d.get("finding") or {}
        text = (
            f"{d.get('flagged_by')} flagged {finding.get('check_id')} "
            f"(severity {finding.get('severity')}, "
            f"observed {finding.get('observed')!r})"
        )
        count = d.get("finding_count")
        if count and count > 1:
            text += f"; {count} findings"
        cleared_by = d.get("cleared_by") or []
        if cleared_by:
            text += f"; cleared by {', '.join(cleared_by)}"
        abstained = d.get("abstained") or []
        if abstained:
            text += f"; abstained {', '.join(abstained)}"
        parts.append(text)
    return " | ".join(parts)


def to_csv(entries: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["at", "operator", "action", "verdict", "note",
                     "dissent", "entry_hash"])
    for e in entries:
        r = e["result"]
        dissent = _format_dissent(r.get("dissent", []))
        writer.writerow([e["ts"], e["operator"], e["action"],
                         r["verdict"], r.get("note", ""), dissent,
                         e["hash"]])
    return buf.getvalue()


def to_otlp(entries: list[dict]) -> str:
    records = []
    for e in entries:
        r = e["result"]
        records.append({
            "timeUnixNano": str(int(e["ts"]) * 1_000_000_000),
            "severityText": {"clear": "INFO", "flagged": "WARN",
                             "contested": "WARN",
                             "blocked": "ERROR"}[r["verdict"]],
            "body": {"stringValue": e["action"]},
            "attributes": [
                {"key": "witness_gate.verdict",
                 "value": {"stringValue": r["verdict"]}},
                {"key": "witness_gate.operator",
                 "value": {"stringValue": e["operator"]}},
                {"key": "witness_gate.entry_hash",
                 "value": {"stringValue": e["hash"]}},
                {"key": "witness_gate.dissent_count",
                 "value": {"intValue": str(len(r.get("dissent", [])))}},
            ],
        })
    return json.dumps({"resourceLogs": [{
        "resource": {"attributes": [
            {"key": "service.name",
             "value": {"stringValue": "witness-gate"}}]},
        "scopeLogs": [{"logRecords": records}],
    }]}, indent=2)


FORMATS = {"json": to_json, "csv": to_csv, "otlp": to_otlp}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="export")
    parser.add_argument("ledger")
    parser.add_argument("--format", choices=list(FORMATS), default="json")
    args = parser.parse_args(argv)
    if not verify_ledger(args.ledger):
        print("ledger does not verify: the hash chain is broken",
              file=sys.stderr)
        return 1
    sys.stdout.write(FORMATS[args.format](read_ledger(args.ledger)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
