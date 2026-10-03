#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

from decision_index import editions
from decision_index.suite.build.adapters_added import ORDER as ADDED_ORDER
from decision_index.suite.build.rebuild import BUILDERS
from decision_index.suite.io import Suite, sha256_file

from artifact_layout import artifact_prefix, artifact_root, sha256, validate_shard
from stack_config import load_stack


def run_logged(command: list[str], log_path: Path) -> None:
    with log_path.open("w") as log:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log.write(line)
        returncode = process.wait()
    if returncode:
        raise RuntimeError(f"command exited with {returncode}: {command}")


def download_artifacts(repo: str, prefix: str, destination: Path) -> None:
    api = HfApi()
    files = api.list_repo_files(repo_id=repo, repo_type="dataset")
    wanted = [
        filename
        for filename in files
        if filename.startswith(f"{prefix}/base/")
        or filename.startswith(f"{prefix}/added/")
    ]
    if not wanted:
        raise RuntimeError(f"no Decision Index shards found under {prefix} in {repo}")
    for filename in wanted:
        hf_hub_download(
            repo_id=repo,
            repo_type="dataset",
            filename=filename,
            local_dir=destination,
        )


def copy_base_normalized(download: Path, stack: dict, build_work: Path) -> list[dict]:
    normalized = build_work / "artifacts/benchmark-suite/normalized"
    normalized.mkdir(parents=True, exist_ok=True)
    records = []

    for catalog_id in sorted(int(value) for value in BUILDERS):
        shard = download / artifact_prefix(stack, "base", catalog_id)
        manifest = validate_shard(shard, stack, "base", catalog_id)
        source_dir = shard / "normalized"
        files = sorted(source_dir.glob("*.jsonl"))
        if not files:
            raise RuntimeError(f"base shard {catalog_id} has no normalized files")
        for source in files:
            target = normalized / source.name
            if target.exists():
                if sha256(target) != sha256(source):
                    raise RuntimeError(f"conflicting normalized file: {source.name}")
            else:
                shutil.copy2(source, target)
        records.append(
            {
                "catalog_id": catalog_id,
                "manifest_sha256": sha256(shard / "manifest.json"),
                "normalized_files": [path.name for path in files],
                "normalized_bytes": manifest["normalized_bytes"],
            }
        )
    return records


def combine_added(download: Path, stack: dict, output: Path) -> list[dict]:
    records = []
    with output.open("wb") as combined:
        for catalog_id in ADDED_ORDER:
            shard = download / artifact_prefix(stack, "added", int(catalog_id))
            manifest = validate_shard(shard, stack, "added", int(catalog_id))
            source = shard / "added-rows.jsonl"
            if not source.exists():
                raise RuntimeError(f"added shard {catalog_id} has no added-rows.jsonl")
            data = source.read_bytes()
            if data and not data.endswith(b"\n"):
                raise RuntimeError(f"added shard {catalog_id} does not end with a newline")
            combined.write(data)
            records.append(
                {
                    "catalog_id": int(catalog_id),
                    "manifest_sha256": sha256(shard / "manifest.json"),
                    "rows": manifest["rows"],
                    "bytes": len(data),
                }
            )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--decision-index", required=True, type=Path)
    parser.add_argument("--stack", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if not os.environ.get("HF_TOKEN"):
        raise SystemExit("HF_TOKEN is required")

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    stack = load_stack(args.stack)
    edition_id = stack["decision_index"]["edition"]
    edition = editions.get(edition_id)
    root = artifact_root(stack)

    download = args.work / "download"
    build_work = args.work / "rebuild"
    combined_added = args.work / "combined-added-rows.jsonl"
    for path in (download, build_work):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)

    download_artifacts(args.repo, root, download)
    base_records = copy_base_normalized(download, stack, build_work)
    added_records = combine_added(download, stack, combined_added)

    base_ids = sorted(int(value) for value in BUILDERS)
    run_logged(
        [
            str(args.decision_index),
            "suite",
            "rebuild",
            "--edition",
            edition_id,
            "--work",
            str(build_work),
            "--skip-download",
            "--skip-normalize",
            "--only",
            *[str(value) for value in base_ids],
        ],
        args.work / "assemble-base.log",
    )

    selected_rows = (
        build_work
        / "artifacts/benchmark-suite/release-v2-rebuilt/selected-rows.jsonl.gz"
    )
    if not selected_rows.exists():
        raise RuntimeError("canonical base assembly did not produce selected-rows.jsonl.gz")

    rows_digest = sha256_file(selected_rows, gunzip=True)
    if rows_digest != edition["rows_sha256"]:
        raise RuntimeError(
            f"base rows hash mismatch: {rows_digest} != {edition['rows_sha256']}"
        )

    added_digest = sha256(combined_added)
    if added_digest != edition["added_sha256"]:
        raise RuntimeError(
            f"added rows hash mismatch: {added_digest} != {edition['added_sha256']}"
        )

    if args.output.exists():
        shutil.rmtree(args.output)

    run_logged(
        [
            str(args.decision_index),
            "suite",
            "import",
            "--edition",
            edition_id,
            "--dir",
            str(args.output),
            "--rows",
            str(selected_rows),
            "--added-rows",
            str(combined_added),
        ],
        args.work / "suite-import.log",
    )

    verification = Suite(args.output, edition_id).verify(strict=True)
    provenance = {
        "decision_index": stack["decision_index"],
        "source_repo": args.repo,
        "source_prefix": root,
        "base_shards": base_records,
        "added_shards": added_records,
        "verification": verification,
    }
    (args.output / "systemone-manifest.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    print(json.dumps(provenance, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
