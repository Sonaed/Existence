#!/usr/bin/env python3
"""Create a validated Existence benchmark record from a completed run."""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from performance_registry import make_record, save


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--input", default="generated fixture")
    parser.add_argument("--command", required=True, help="Command that produced the measurement")
    parser.add_argument("--metrics", required=True, help='JSON object, e.g. {"elapsed_ms": 12.4}')
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    try:
        metrics = json.loads(args.metrics)
        record = make_record(app=args.app, scenario=args.scenario, command=shlex.split(args.command),
                             input_file=args.input, metrics=metrics, samples=args.samples,
                             app_root=args.app_root, notes=args.notes)
        print(save(args.output, record))
    except (ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
