"""Command-line interface for VibeCheck-AI."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional

from .config import Settings
from .engine import VibeCheck
from .logging_setup import configure_logging
from .mockdata import generate
from .version import __version__


def _reconfigure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def _settings(args) -> Settings:
    s = Settings.from_env()
    if getattr(args, "db", None):
        s.database_url = args.db
    return s


def cmd_demo(args) -> int:
    s = _settings(args)
    s.database_url = args.db or ":memory:"
    vc = VibeCheck(s)
    t0 = time.time()
    result = vc.ingest_many(generate(args.count, seed=args.seed))
    elapsed = time.time() - t0
    vc.analytics.rebuild()
    alerts = vc.run_alerts()
    stats = vc.stats()

    print(f"VibeCheck demo — ingested {args.count} tickets in {elapsed:.2f}s "
          f"({args.count/elapsed:,.0f}/s)")
    print(f"  accepted={result['accepted']}  noise_filtered={result['noise']}  "
          f"clusters={stats['clusters']}  cache_hit_rate={stats['cache']['hit_rate']:.0%}")
    print("\nTop roadmap items (what to fix first):")
    for i, item in enumerate(vc.roadmap(limit=args.top), 1):
        c = item.cluster
        print(f"  {i:2d}. [{item.score:5.1f}] {c.label:<20} "
              f"size={c.size:<4} sev={c.avg_severity:.1f}  ({item.rationale})")
    print(f"\nAlerts routed to Slack/Jira: {len(alerts)}")
    for a in alerts[:args.top]:
        print(f"  -> {'+'.join(a.channels):<10} {a.title}")
    vc.close()
    return 0


def cmd_ingest(args) -> int:
    vc = VibeCheck(_settings(args))
    n = 0
    src = sys.stdin if args.file == "-" else open(args.file, encoding="utf-8")
    try:
        for line in src:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                text = obj.get("text", "")
            except json.JSONDecodeError:
                text = line
            if text:
                vc.pipeline.ingest_text(text)
                n += 1
    finally:
        if src is not sys.stdin:
            src.close()
    vc.analytics.rebuild()
    print(f"Ingested {n} messages. Stats: {json.dumps(vc.stats())}")
    vc.close()
    return 0


def cmd_roadmap(args) -> int:
    vc = VibeCheck(_settings(args))
    items = [it.to_dict() for it in vc.roadmap(limit=args.top)]
    print(json.dumps(items, indent=2))
    vc.close()
    return 0


def cmd_stats(args) -> int:
    vc = VibeCheck(_settings(args))
    print(json.dumps(vc.stats(), indent=2))
    vc.close()
    return 0


def cmd_serve(args) -> int:
    from .services.api import run_server

    run_server(host=args.host, port=args.port, db=args.db or "vibecheck.db")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vibecheck", description="AI customer-feedback analytics engine")
    p.add_argument("--version", action="version", version=f"vibecheck {__version__}")
    p.add_argument("--db", default=None, help="SQLite database path")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="generate synthetic tickets and show the roadmap")
    d.add_argument("-c", "--count", type=int, default=2000)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--top", type=int, default=10)
    d.set_defaults(func=cmd_demo)

    i = sub.add_parser("ingest", help="ingest messages from a file (jsonl or plain text; - for stdin)")
    i.add_argument("file")
    i.set_defaults(func=cmd_ingest)

    r = sub.add_parser("roadmap", help="print the prioritised roadmap as JSON")
    r.add_argument("--top", type=int, default=15)
    r.set_defaults(func=cmd_roadmap)

    s = sub.add_parser("stats", help="print platform stats")
    s.set_defaults(func=cmd_stats)

    sv = sub.add_parser("serve", help="run the FastAPI web-api + dashboard")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    _reconfigure_stdout()
    args = build_parser().parse_args(argv)
    configure_logging("DEBUG" if args.verbose else "WARNING")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
