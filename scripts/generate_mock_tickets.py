#!/usr/bin/env python3
"""Flood the platform with realistic mock feedback.

Usage:
    python scripts/generate_mock_tickets.py                 # 5,000 tickets -> vibecheck.db
    python scripts/generate_mock_tickets.py -n 20000        # 20k tickets
    python scripts/generate_mock_tickets.py --jsonl out.jsonl   # just write JSONL, no ingest
    python scripts/generate_mock_tickets.py --post http://localhost:8000/webhook

The default path ingests directly through the pipeline (no server needed) and
prints throughput plus the resulting roadmap — a one-command demo of the whole
engine.
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Generate realistic mock feedback tickets")
    ap.add_argument("-n", "--count", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--db", default="vibecheck.db")
    ap.add_argument("--jsonl", default=None, help="write events to a JSONL file instead of ingesting")
    ap.add_argument("--post", default=None, help="POST each event to a webhook URL")
    args = ap.parse_args(argv)

    from vibecheck.mockdata import generate_events

    if args.jsonl:
        with open(args.jsonl, "w", encoding="utf-8") as f:
            for evt in generate_events(args.count, seed=args.seed):
                f.write(json.dumps(evt) + "\n")
        print(f"Wrote {args.count} events to {args.jsonl}")
        return 0

    if args.post:
        import urllib.request
        t0 = time.time()
        for evt in generate_events(args.count, seed=args.seed):
            data = json.dumps(evt).encode()
            req = urllib.request.Request(args.post, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)  # noqa: S310
        print(f"Posted {args.count} events to {args.post} in {time.time()-t0:.1f}s")
        return 0

    # direct ingest through the pipeline
    from vibecheck.config import Settings
    from vibecheck.engine import VibeCheck
    from vibecheck.mockdata import generate

    settings = Settings.from_env()
    settings.database_url = args.db
    vc = VibeCheck(settings)

    t0 = time.time()
    res = vc.ingest_many(generate(args.count, seed=args.seed))
    elapsed = time.time() - t0

    vc.analytics.rebuild()
    alerts = vc.run_alerts()
    stats = vc.stats()

    print(f"Ingested {args.count} tickets in {elapsed:.2f}s "
          f"({args.count/elapsed:,.0f} tickets/sec)")
    print(f"  accepted={res['accepted']}  noise_filtered={res['noise']}  "
          f"topics={stats['clusters']}  bugs={stats['bugs']}  "
          f"cache_hit_rate={stats['cache']['hit_rate']:.0%}  alerts={len(alerts)}")
    print("\nTop roadmap:")
    for i, item in enumerate(vc.roadmap(limit=10), 1):
        c = item.cluster
        print(f"  {i:2d}. [{item.score:5.1f}] {c.label:<22} size={c.size:<4} "
              f"sev={c.avg_severity:.1f}  ({item.rationale})")
    vc.close()
    print(f"\nWrote {args.db}. Run `vibecheck serve --db {args.db}` and open http://localhost:8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
