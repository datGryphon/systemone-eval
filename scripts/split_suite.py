#!/usr/bin/env python3
import argparse
import gzip
import json
import random
from pathlib import Path

from decision_index.suite.io import Suite


SHUFFLE_SEED = 0x53595331


def rows_from_file(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--suite", type=Path)
    source.add_argument("--rows", type=Path)
    parser.add_argument("--edition")
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--shards", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.suite and not args.edition:
        parser.error("--edition is required with --suite")

    if not 0 <= args.shard < args.shards:
        raise ValueError("shard must be between 0 and shards - 1")

    totals = [0] * args.shards
    counts = [0] * args.shards
    rows = []

    source_rows = (
        Suite(args.suite, args.edition).rows(apply_exclusions=True)
        if args.suite
        else rows_from_file(args.rows)
    )

    for row in source_rows:
        weight = row["_evaluation"]["proxy_tokens"]
        shard = min(range(args.shards), key=lambda i: (totals[i], counts[i], i))
        totals[shard] += weight
        counts[shard] += 1
        if shard == args.shard:
            rows.append(row)

    random.Random(SHUFFLE_SEED + args.shard).shuffle(rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", encoding="utf-8") as output:
        for row in rows:
            output.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )

    print(
        f"shard {args.shard}/{args.shards}: {counts[args.shard]} rows, "
        f"{totals[args.shard]} proxy tokens "
        f"(range {min(totals)}-{max(totals)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
