#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path

from decision_index.suite.build.adapters_added import ORDER
from decision_index.suite.build.rebuild import BUILDERS


# BRIGHT reads ToolRet's retrieval mapping during normalization.
SOURCE_DEPENDENCIES = {2: "retrieval", 36: "retrieval"}


def base_groups() -> list[dict]:
    groups = defaultdict(list)

    for catalog_id, builder in BUILDERS.items():
        identity = SOURCE_DEPENDENCIES.get(int(catalog_id))
        if identity is None:
            identity = (builder.__module__, builder.__qualname__)
        groups[identity].append(int(catalog_id))

    return [
        {
            "key": "-".join(f"{catalog_id:03d}" for catalog_id in ids),
            "catalog_ids": " ".join(str(catalog_id) for catalog_id in ids),
        }
        for ids in sorted((sorted(ids) for ids in groups.values()))
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    base = base_groups()
    added = [
        {"key": f"{int(catalog_id):03d}", "catalog_id": int(catalog_id)}
        for catalog_id in ORDER
    ]

    if args.github_output:
        with args.github_output.open("a") as output:
            print(f"base={json.dumps({'include': base}, separators=(',', ':'))}", file=output)
            print(f"added={json.dumps({'include': added}, separators=(',', ':'))}", file=output)
            print(
                "base-ids=" + " ".join(str(catalog_id) for catalog_id in sorted(BUILDERS)),
                file=output,
            )

    print(json.dumps({"base": base, "added": added}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
