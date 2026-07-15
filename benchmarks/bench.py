#!/usr/bin/env python3
"""Throughput + cache-savings benchmark.

Measures:
  * end-to-end ingest throughput (tickets/sec) through the full pipeline
  * LLM API-call savings from the enrichment cache (hit-rate → % calls avoided)

Runs entirely offline with the deterministic mock enricher, so numbers are
reproducible on any machine (absolute throughput varies with hardware).
"""

from __future__ import annotations

import argparse
import sys
import time


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--count", type=int, default=5000)
    args = ap.parse_args(argv)

    from vibecheck.config import Settings
    from vibecheck.engine import VibeCheck
    from vibecheck.mockdata import generate

    settings = Settings()
    settings.database_url = ":memory:"
    vc = VibeCheck(settings)

    tickets = list(generate(args.count, seed=7))
    t0 = time.perf_counter()
    res = vc.ingest_many(tickets)
    elapsed = time.perf_counter() - t0

    t1 = time.perf_counter()
    clusters = vc.analytics.rebuild()
    cluster_elapsed = time.perf_counter() - t1

    stats = vc.stats()
    cache = stats["cache"]
    calls_saved = cache["hits"]
    naive_calls = cache["total"]
    savings_pct = 100 * calls_saved / naive_calls if naive_calls else 0.0

    print("=" * 64)
    print("VibeCheck-AI benchmark")
    print("=" * 64)
    print(f"tickets processed      : {args.count}")
    print(f"  accepted             : {res['accepted']}")
    print(f"  noise filtered       : {res['noise']} ({100*res['noise']/args.count:.1f}%)")
    print(f"ingest wall time       : {elapsed:.3f}s")
    print(f"ingest throughput      : {args.count/elapsed:,.0f} tickets/sec")
    print(f"clustering wall time   : {cluster_elapsed:.3f}s ({len(clusters)} topics)")
    print("-" * 64)
    print(f"enrichment calls (naive): {naive_calls}")
    print(f"cache hits (avoided)    : {calls_saved}")
    print(f"LLM API-call savings    : {savings_pct:.1f}%")
    print("=" * 64)
    vc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
