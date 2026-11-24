"""Panel latency: what one judgment costs, measured, not promised.

    python benchmarks/latency.py [calls]
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from soul_cradle.assessors import panel

PACKET = {"principal_consent": True, "fully_disclosed": True,
          "reversible": True, "deception_involved": False,
          "affected_parties": ["customer"], "disproportionate_harm": False,
          "contradicts_commitments": False, "sustains_long_term": True,
          "hidden_costs_addressed": True, "safe_on_repetition": True,
          "strengthens_relationship": True, "precedent_setting": False,
          "variance": "low", "actor": "bench", "action_type": "refund"}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    panel("warmup", PACKET)
    times = []
    for _ in range(n):
        start = time.perf_counter()
        panel("Benchmark action", PACKET)
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    print(f"panel calls: {n}")
    print(f"mean:   {statistics.mean(times):.2f} ms")
    print(f"median: {statistics.median(times):.2f} ms")
    print(f"p95:    {times[int(n * 0.95) - 1]:.2f} ms")
    print(f"max:    {times[-1]:.2f} ms")


if __name__ == "__main__":
    main()
