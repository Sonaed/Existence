#!/usr/bin/env python3
"""Validate every committed `existence.benchmark.v1` record below a root."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from performance_registry import FORMAT, validate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=HERE.parent)
    args = parser.parse_args()
    records = []
    failures = []
    for path in sorted(args.root.glob("*/docs/benchmarks/*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{path}: unreadable ({exc})")
            continue
        if record.get("format") != FORMAT:
            continue
        errors = validate(record)
        if errors:
            failures.append(f"{path}: " + "; ".join(errors))
        else:
            records.append(path)
    for failure in failures:
        print("FAIL", failure)
    print(f"{len(records)} valid benchmark record(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
