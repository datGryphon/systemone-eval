#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from decision_index.suite.build.adapters_added import ORDER

from base_groups import base_builder_groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    payload = {
        "base": base_builder_groups(),
        "added": [int(catalog_id) for catalog_id in ORDER],
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n")

    if args.github_output:
        base_matrix = {
            "include": [
                {
                    "key": group["key"],
                    "builder": group["builder"],
                    "catalog_ids_json": json.dumps(
                        group["catalog_ids"],
                        separators=(",", ":"),
                    ),
                }
                for group in payload["base"]
            ]
        }
        with args.github_output.open("a") as output:
            print(
                f"base={json.dumps(base_matrix, separators=(',', ':'))}",
                file=output,
            )
            print(
                f"added={json.dumps(payload['added'], separators=(',', ':'))}",
                file=output,
            )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
