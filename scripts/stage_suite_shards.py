#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path

from decision_index.suite.build.adapters_added import ORDER


def copy_normalized(source: Path, destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(source.glob("base/*/normalized/*.jsonl")):
        target = destination / path.name
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise RuntimeError(f"conflicting normalized shard: {path.name}")
        if not target.exists():
            shutil.copy2(path, target)
            count += 1
    if not any(destination.glob("*.jsonl")):
        raise RuntimeError("no base normalized shards found")
    return count


def combine_added(source: Path, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with output.open("wb") as combined:
        for catalog_id in ORDER:
            path = source / "added" / f"{int(catalog_id):03d}" / "added-rows.jsonl"
            if not path.exists():
                raise RuntimeError(f"missing added shard: {path}")
            data = path.read_bytes()
            if data and not data.endswith(b"\n"):
                raise RuntimeError(f"added shard lacks trailing newline: {path}")
            combined.write(data)
            rows += data.count(b"\n")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--added-out", required=True, type=Path)
    args = parser.parse_args()

    normalized = args.work / "artifacts/benchmark-suite/normalized"
    copied = copy_normalized(args.source, normalized)
    rows = combine_added(args.source, args.added_out)
    print(f"staged {copied} normalized files and {rows} added rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
