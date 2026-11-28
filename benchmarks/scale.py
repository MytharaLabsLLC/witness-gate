"""Scale envelope: sustained throughput and ledger growth, measured.

    python benchmarks/scale.py

Two measurements, both with the configuration a real deployment runs:
a Gate with a sealed ledger attached, so every check pays the panel
judgment, the hash, and the append.

1. Throughput: sealed Gate.check calls back to back for a fixed
   30 second window in one process. Reports checks per second and the
   mean and p95 per-call latency.

2. Ledger growth: one ledger grown in a single pass through 10,000,
   100,000, and 1,000,000 entries. At each size, the total append time
   to reach that size and a full-chain verify_ledger() time.

Raw numbers are printed as they land and saved to
benchmarks/scale-results.json. The big ledger is built in a temp
directory and deleted afterwards; it is about 4 GB at 1M entries.
"""
import json
import os
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from soul_cradle.plug import Gate, verify_ledger

PACKET = {"principal_consent": True, "fully_disclosed": True,
          "reversible": True, "deception_involved": False,
          "affected_parties": ["customer"], "disproportionate_harm": False,
          "contradicts_commitments": False, "sustains_long_term": True,
          "hidden_costs_addressed": True, "safe_on_repetition": True,
          "strengthens_relationship": True, "precedent_setting": False,
          "variance": "low", "actor": "bench", "action_type": "refund"}

WINDOW_SECONDS = 30.0
SIZES = [10_000, 100_000, 1_000_000]


def throughput(tmpdir):
    path = os.path.join(tmpdir, "throughput.jsonl")
    gate = Gate(operator="bench-throughput", ledger_path=path)
    for i in range(200):
        gate.check(f"warmup {i}", PACKET)
    times = []
    start = time.perf_counter()
    deadline = start + WINDOW_SECONDS
    i = 0
    while True:
        t0 = time.perf_counter()
        gate.check(f"Throughput action {i}", PACKET)
        times.append((time.perf_counter() - t0) * 1000)
        i += 1
        if time.perf_counter() >= deadline:
            break
    elapsed = time.perf_counter() - start
    times.sort()
    result = {
        "checks": len(times),
        "window_seconds": round(elapsed, 2),
        "checks_per_second": round(len(times) / elapsed, 1),
        "mean_ms": round(statistics.mean(times), 3),
        "p95_ms": round(times[int(len(times) * 0.95) - 1], 3),
        "median_ms": round(statistics.median(times), 3),
        "max_ms": round(times[-1], 3),
    }
    print(f"THROUGHPUT {json.dumps(result)}", flush=True)
    return result


def growth(tmpdir):
    path = os.path.join(tmpdir, "growth.jsonl")
    gate = Gate(operator="bench-growth", ledger_path=path)
    rows = []
    done = 0
    append_start = time.perf_counter()
    for size in SIZES:
        while done < size:
            gate.check(f"Growth action {done}", PACKET)
            done += 1
        append_total = time.perf_counter() - append_start
        t0 = time.perf_counter()
        ok = verify_ledger(path)
        verify_seconds = time.perf_counter() - t0
        row = {
            "entries": size,
            "append_total_seconds": round(append_total, 2),
            "append_ms_per_entry": round(append_total / size * 1000, 3),
            "verify_seconds": round(verify_seconds, 2),
            "verify_ok": ok,
            "file_bytes": os.path.getsize(path),
        }
        rows.append(row)
        print(f"GROWTH {json.dumps(row)}", flush=True)
    return rows


def main():
    # Scratch space lives beside the repo, never in the system temp
    # dir: the 1M-entry ledger is about 4 GB and /tmp may be a small
    # tmpfs. (A first run filled a 512 MB /tmp and died at ~65k
    # entries; that is why this is explicit.)
    scratch = os.path.join(os.path.dirname(__file__), "..", "scratch")
    os.makedirs(scratch, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="wg-scale-", dir=scratch)
    print(f"temp dir: {tmpdir}", flush=True)
    results = {"throughput": throughput(tmpdir), "growth": growth(tmpdir)}
    out = os.path.join(os.path.dirname(__file__), "scale-results.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"saved: {out}", flush=True)


if __name__ == "__main__":
    main()
