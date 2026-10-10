#!/usr/bin/env python3
import argparse
import gzip
import json
import random
from pathlib import Path
from types import SimpleNamespace

from decision_index.scoring.index02 import spec
from decision_index.suite.sample import stratified_sample

from decision_index.suite.io import Suite, read_jsonl


SHUFFLE_SEED = 0x53595331



def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--suite", type=Path)
    source.add_argument("--rows", type=Path)
    parser.add_argument("--edition")
    parser.add_argument("--sample-rows", type=int, default=0)
    parser.add_argument("--areas", default="")
    parser.add_argument("--benchmarks", default="")
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--shards", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if (args.suite or args.areas) and not args.edition:
        parser.error("--edition is required with --suite or --areas")
    if args.sample_rows < 0:
        parser.error("--sample-rows cannot be negative")

    if not 0 <= args.shard < args.shards:
        raise ValueError("shard must be between 0 and shards - 1")

    totals = [0] * args.shards
    counts = [0] * args.shards
    rows = []

    source_rows = (
        Suite(args.suite, args.edition).rows(apply_exclusions=True)
        if args.suite
        else read_jsonl(args.rows)
    )

    selected = set()
    if args.areas:
        areas = {area["id"]: area["benchmarks"] for area in spec(args.edition)["areas"]}
        for name in args.areas.split(","):
            name = name.strip()
            if name not in areas:
                parser.error(f"unknown area: {name}")
            selected.update(areas[name])
    if args.benchmarks:
        try:
            selected.update(int(i.strip()) for i in args.benchmarks.split(","))
        except ValueError:
            parser.error("--benchmarks must contain comma-separated integer IDs")
    if selected:
        source_rows = (row for row in source_rows if row["_evaluation"]["catalog_id"] in selected)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.sample_rows:
        sampled = args.out.with_name("sample-rows.jsonl.gz")
        stratified_sample(SimpleNamespace(rows=lambda apply_exclusions=True: source_rows), args.sample_rows, sampled)
        source_rows = read_jsonl(sampled)

    for row in source_rows:
        weight = row["_evaluation"]["proxy_tokens"]
        shard = min(range(args.shards), key=lambda i: (totals[i], counts[i], i))
        totals[shard] += weight
        counts[shard] += 1
        if shard == args.shard:
            rows.append(row)

    if not any(counts):
        parser.error("filters matched no rows")

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
