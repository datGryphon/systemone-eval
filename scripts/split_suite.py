#!/usr/bin/env python3
import argparse
import gzip
import json
from pathlib import Path

from decision_index.suite.io import Suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--shards", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if not 0 <= args.shard < args.shards:
        raise ValueError("shard must be between 0 and shards - 1")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(args.out, "wt", encoding="utf-8") as output:
        for index, row in enumerate(Suite(args.suite, args.edition).rows(apply_exclusions=True)):
            if index % args.shards == args.shard:
                output.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                count += 1

    print(f"shard {args.shard}/{args.shards}: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
