#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path

from decision_index.suite.build.adapters_added import ORDER
from decision_index.suite.build.rebuild import BUILDERS


def base_groups() -> list[dict]:
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    builders = {}

    for catalog_id, builder in BUILDERS.items():
        identity = (builder.__module__, builder.__qualname__)
        grouped[identity].append(int(catalog_id))
        builders[identity] = builder

    groups = []
    for identity, catalog_ids in grouped.items():
        ids = sorted(catalog_ids)
        builder = builders[identity]
        groups.append(
            {
                "key": "-".join(f"{catalog_id:03d}" for catalog_id in ids),
                "builder": f"{builder.__module__.rsplit('.', 1)[-1]}.{builder.__name__}",
                "catalog_ids": " ".join(str(catalog_id) for catalog_id in ids),
            }
        )
    return sorted(groups, key=lambda group: [int(x) for x in group["catalog_ids"].split()])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    base = base_groups()
    added = [
        {"key": f"{int(catalog_id):03d}", "catalog_id": int(catalog_id)}
        for catalog_id in ORDER
    ]
    payload = {"base": base, "added": added}

    if args.github_output:
        with args.github_output.open("a") as output:
            print(
                f"base={json.dumps({'include': base}, separators=(',', ':'))}",
                file=output,
            )
            print(
                f"added={json.dumps({'include': added}, separators=(',', ':'))}",
                file=output,
            )

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
