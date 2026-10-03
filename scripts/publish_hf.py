#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError

from artifact_layout import (
    artifact_prefix,
    validate_added_shard,
    validate_base_shard,
    validate_suite,
)
from stack_config import load_stack


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--stack", required=True, type=Path)
    parser.add_argument("--kind", required=True, choices=("base", "added", "suite"))
    parser.add_argument("--catalog-id", type=int)
    parser.add_argument("--group-key")
    parser.add_argument("--catalog-ids-json")
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()

    if not os.environ.get("HF_TOKEN"):
        raise SystemExit("HF_TOKEN is required")
    if not args.source.is_dir():
        raise SystemExit(f"artifact directory not found: {args.source}")

    stack = load_stack(args.stack)
    if args.kind == "suite":
        validate_suite(args.source, stack)
        prefix = artifact_prefix(stack, "suite")
        label = "suite"
    elif args.kind == "base":
        if not args.group_key or not args.catalog_ids_json:
            raise ValueError("base artifacts require --group-key and --catalog-ids-json")
        catalog_ids = json.loads(args.catalog_ids_json)
        validate_base_shard(args.source, stack, args.group_key, catalog_ids)
        prefix = artifact_prefix(stack, "base", group_key=args.group_key)
        label = args.group_key
    else:
        if args.catalog_id is None:
            raise ValueError("added artifacts require --catalog-id")
        validate_added_shard(args.source, stack, args.catalog_id)
        prefix = artifact_prefix(stack, "added", catalog_id=args.catalog_id)
        label = str(args.catalog_id)

    api = HfApi(token=os.environ["HF_TOKEN"])
    info = None
    for attempt in range(6):
        try:
            info = api.upload_folder(
                repo_id=args.repo,
                repo_type="dataset",
                folder_path=str(args.source),
                path_in_repo=prefix,
                ignore_patterns=["rebuild.log", "published.json"],
                commit_message=f"systemone-eval: publish {args.kind} {label}",
            )
            break
        except HfHubHTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status not in {409, 412} or attempt == 5:
                raise
            delay = 2 ** attempt
            print(f"Hub commit raced another shard upload; retrying in {delay}s")
            time.sleep(delay)

    assert info is not None
    published = {
        "repo": args.repo,
        "path": prefix,
        "kind": args.kind,
        "catalog_id": args.catalog_id,
        "group_key": args.group_key,
        "commit_oid": getattr(info, "oid", None),
        "commit_url": getattr(info, "commit_url", None),
    }
    (args.source / "published.json").write_text(json.dumps(published, indent=2) + "\n")
    print(json.dumps(published, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
