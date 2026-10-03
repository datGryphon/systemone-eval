#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from decision_index.suite.build.adapters_added import ORDER

from base_groups import base_builder_groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    payload = {
        "base": base_builder_groups(),
        "added": [int(catalog_id) for catalog_id in ORDER],
    }

    if args.github_output:
        with args.github_output.open("a") as output:
            print(
                f"base={json.dumps(payload['base'], separators=(',', ':'))}",
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
