import csv
import io
import json

import pytest

from soul_cradle import Gate
from soul_cradle.evidence import ConsentBook, build_evidence
from soul_cradle.export import to_csv, to_json, to_otlp
from soul_cradle.review import decide, holds


def test_consent_comes_from_the_book_not_the_caller(tmp_path):
    book = ConsentBook(str(tmp_path / "consent.jsonl"))
    packet = build_evidence("send_email", {"recipient": "a@b.c"},
                            principal="a@b.c", consent_book=book,
                            principal_consent=True)  # caller claims yes
    assert packet["principal_consent"] is False  # book says no record
    book.record("a@b.c", "send_email")
    packet = build_evidence("send_email", {"recipient": "a@b.c"},
                            principal="a@b.c", consent_book=book)
    assert packet["principal_consent"] is True


def test_derived_reversibility_and_parties():
    packet = build_evidence("delete", {"customer_id": "c-9"})
    assert packet["reversible"] is False
    assert packet["affected_parties"] == ["c-9"]
    packet = build_evidence("draft", {})
    assert packet["reversible"] is True


def _ledger_with_hold(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    gate = Gate(operator="test", ledger_path=path)
    gate.check("sparse packet action", {"principal_consent": True})
    gate.check("deceptive action", {"deception_involved": True})
    return path


def test_review_lists_holds_and_records_decisions(tmp_path):
    path = _ledger_with_hold(tmp_path)
    pending = holds(path)
    assert {e["result"]["verdict"] for e in pending} == {"flagged", "blocked"}
    flagged = next(e for e in pending
                   if e["result"]["verdict"] == "flagged")
    decide(path, flagged["hash"], "approved", "dana")
    assert [e["result"]["verdict"] for e in holds(path)] == ["blocked"]


def test_blocked_cannot_be_approved(tmp_path):
    path = _ledger_with_hold(tmp_path)
    blocked = next(e for e in holds(path)
                   if e["result"]["verdict"] == "blocked")
    with pytest.raises(ValueError):
        decide(path, blocked["hash"], "approved", "dana")
    decide(path, blocked["hash"], "acknowledged", "dana")


def test_cli_entry_points(tmp_path, capsys):
    from soul_cradle.export import main as export_main
    from soul_cradle.review import main as review_main
    path = _ledger_with_hold(tmp_path)
    assert review_main(["list", "--ledger", path]) == 0
    assert "blocked" in capsys.readouterr().out
    assert export_main([path, "--format", "csv"]) == 0
    assert "verdict" in capsys.readouterr().out


def test_exports(tmp_path):
    path = _ledger_with_hold(tmp_path)
    from soul_cradle.review import read_ledger
    entries = read_ledger(path)
    assert len(json.loads(to_json(entries))) == 2
    csv_text = to_csv(entries)
    assert "flagged" in csv_text and "blocked" in csv_text
    assert "None:None" not in csv_text
    otlp = json.loads(to_otlp(entries))
    records = otlp["resourceLogs"][0]["scopeLogs"][0]["logRecords"]
    assert len(records) == 2
    assert records[1]["severityText"] == "ERROR"


def test_csv_export_carries_the_dissent(tmp_path):
    from soul_cradle.review import read_ledger
    path = str(tmp_path / "ledger.jsonl")
    gate = Gate(operator="test", ledger_path=path)
    packet = {
        "principal_consent": True, "fully_disclosed": True,
        "reversible": True, "deception_involved": False,
        "affected_parties": ["customer"], "disproportionate_harm": False,
        "contradicts_commitments": False, "sustains_long_term": True,
        "hidden_costs_addressed": True, "safe_on_repetition": True,
        "strengthens_relationship": True, "precedent_setting": False,
        "variance": "high",
    }
    result = gate.check("high variance refund", packet)
    assert result.verdict == "contested"
    csv_text = to_csv(read_ledger(path))
    assert "None:None" not in csv_text
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    dissent_cell = rows[0]["dissent"]
    # The cell names the dissent the panel actually recorded: who
    # flagged, on what check, and who cleared the same action.
    assert "dionysus" in dissent_cell
    assert "dionysus.variance" in dissent_cell
    assert "demeter" in dissent_cell
