#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from huggingface_hub import HfApi

from artifact_layout import artifact_prefix, validate_shard, validate_suite
from stack_config import load_stack


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--stack", required=True, type=Path)
    parser.add_argument("--kind", required=True, choices=("base", "added", "suite"))
    parser.add_argument("--catalog-id", type=int)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()

    if not os.environ.get("HF_TOKEN"):
        raise SystemExit("HF_TOKEN is required")
    if not args.source.is_dir():
        raise SystemExit(f"artifact directory not found: {args.source}")

    stack = load_stack(args.stack)
    if args.kind == "suite":
        validate_suite(args.source)
    else:
        if args.catalog_id is None:
            raise ValueError(f"{args.kind} artifacts require a catalog ID")
        validate_shard(args.source, stack, args.kind, args.catalog_id)
    prefix = artifact_prefix(stack, args.kind, args.catalog_id)

    api = HfApi()
    info = api.upload_folder(
        repo_id=args.repo,
        repo_type="dataset",
        folder_path=str(args.source),
        path_in_repo=prefix,
        ignore_patterns=["rebuild.log", "published.json"],
        commit_message=f"systemone-eval: publish {args.kind} {args.catalog_id if args.catalog_id is not None else 'suite'}",
    )
    published = {
        "repo": args.repo,
        "path": prefix,
        "kind": args.kind,
        "catalog_id": args.catalog_id,
        "commit_oid": getattr(info, "oid", None),
        "commit_url": getattr(info, "commit_url", None),
    }
    (args.source / "published.json").write_text(json.dumps(published, indent=2) + "\n")
    print(json.dumps(published, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
