#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from huggingface_hub import HfApi

from stack_config import load_stack


def artifact_prefix(stack: dict, kind: str, catalog_id: int | None) -> str:
    decision_index = stack["decision_index"]
    root = f"decision-index/{decision_index['edition']}/{decision_index['ref']}"
    if kind == "suite":
        if catalog_id is not None:
            raise ValueError("suite artifacts do not take a catalog ID")
        return f"{root}/suite"
    if catalog_id is None:
        raise ValueError(f"{kind} artifacts require a catalog ID")
    return f"{root}/{kind}/{catalog_id:03d}"


def validate_source(source: Path, stack: dict, kind: str, catalog_id: int | None) -> None:
    if kind == "suite":
        required = {
            "selected-rows.jsonl.gz",
            "added-rows.jsonl.gz",
            "excluded-questions.json",
            "manifest.json",
        }
        missing = [name for name in required if not (source / name).exists()]
        if missing:
            raise ValueError(f"suite artifact missing files: {missing}")
        return

    manifest_path = source / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"missing shard manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("stack") != stack:
        raise ValueError("shard stack does not match current stack.json")
    if manifest.get("catalog_id") != catalog_id:
        raise ValueError("shard catalog ID does not match publish target")
    expected_kind = {
        "base": "decision-index-base-normalized-shard",
        "added": "decision-index-added-rows-shard",
    }[kind]
    if manifest.get("kind") != expected_kind:
        raise ValueError(f"unexpected shard kind: {manifest.get('kind')}")


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
    validate_source(args.source, stack, args.kind, args.catalog_id)
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
