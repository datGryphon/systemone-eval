import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_root(stack: dict) -> str:
    decision_index = stack["decision_index"]
    return f"decision-index/{decision_index['edition']}/{decision_index['ref']}"


def artifact_prefix(stack: dict, kind: str, catalog_id: int | None = None) -> str:
    root = artifact_root(stack)
    if kind == "suite":
        if catalog_id is not None:
            raise ValueError("suite artifacts do not take a catalog ID")
        return f"{root}/suite"
    if kind not in {"base", "added"}:
        raise ValueError(f"unknown artifact kind: {kind}")
    if catalog_id is None:
        raise ValueError(f"{kind} artifacts require a catalog ID")
    return f"{root}/{kind}/{catalog_id:03d}"


def validate_shard(source: Path, stack: dict, kind: str, catalog_id: int) -> dict:
    manifest_path = source / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"missing shard manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("decision_index") != stack["decision_index"]:
        raise ValueError("shard Decision Index provenance does not match stack.json")
    if manifest.get("catalog_id") != catalog_id:
        raise ValueError("shard catalog ID does not match target")
    expected_kind = {
        "base": "decision-index-base-normalized-shard",
        "added": "decision-index-added-rows-shard",
    }[kind]
    if manifest.get("kind") != expected_kind:
        raise ValueError(f"unexpected shard kind: {manifest.get('kind')}")
    return manifest


def validate_suite(source: Path) -> None:
    required = {
        "selected-rows.jsonl.gz",
        "added-rows.jsonl.gz",
        "excluded-questions.json",
        "manifest.json",
    }
    missing = sorted(name for name in required if not (source / name).exists())
    if missing:
        raise ValueError(f"suite artifact missing files: {missing}")
