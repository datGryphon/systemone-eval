#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path

from decision_index.suite.build.adapters_added import ORDER
from decision_index.suite.build.rebuild import BUILDERS

from systemone_runtime import load_profile


# BRIGHT reads ToolRet's retrieval mapping during normalization.
RETRIEVAL_GROUP = {2, 36}


def base_groups() -> list[dict]:
    groups = defaultdict(list)

    for catalog_id, builder in BUILDERS.items():
        identity = (
            "retrieval"
            if int(catalog_id) in RETRIEVAL_GROUP
            else (builder.__module__, builder.__qualname__)
        )
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
    parser.add_argument("--models", type=Path)
    parser.add_argument("--profile")
    args = parser.parse_args()

    if (args.models is None) != (args.profile is None):
        parser.error("--models and --profile must be used together")

    base = base_groups()
    added = [
        {"key": f"{int(catalog_id):03d}", "catalog_id": int(catalog_id)}
        for catalog_id in ORDER
    ]

    evaluation = None
    profile = None
    if args.models is not None:
        profile = load_profile(args.models, args.profile)
        evaluation = [
            {"profile": args.profile, "shard": shard, "shards": profile.shards}
            for shard in range(profile.shards)
        ]

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
            print(
                "base-ids=" + " ".join(str(catalog_id) for catalog_id in sorted(BUILDERS)),
                file=output,
            )
            if evaluation is not None:
                print(
                    "evaluation="
                    + json.dumps({"include": evaluation}, separators=(",", ":")),
                    file=output,
                )
                print(f"profile={args.profile}", file=output)
                print(f"shards={profile.shards}", file=output)

    result = {"base": base, "added": added}
    if evaluation is not None:
        result["evaluation"] = evaluation
        result["profile"] = args.profile
        result["shards"] = profile.shards
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
