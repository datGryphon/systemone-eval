#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from stack_config import load_stack


def tree_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


class DiskMonitor:
    def __init__(self, path: str = "/", interval: float = 0.25):
        self.path = path
        self.interval = interval
        self.peak_used = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak_used = max(self.peak_used, shutil.disk_usage(self.path).used)
            self._stop.wait(self.interval)

    def start(self) -> None:
        self.peak_used = shutil.disk_usage(self.path).used
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()
        self.peak_used = max(self.peak_used, shutil.disk_usage(self.path).used)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_logged(command: list[str], log_path: Path) -> int:
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
        return process.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-index", required=True, type=Path)
    parser.add_argument("--catalog-id", required=True, type=int)
    parser.add_argument("--stack", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    stack = load_stack(args.stack)
    args.output.mkdir(parents=True, exist_ok=True)
    before = shutil.disk_usage("/")

    monitor = DiskMonitor("/")
    monitor.start()
    started_ns = time.perf_counter_ns()
    try:
        returncode = run_logged(
            [
                str(args.decision_index),
                "suite",
                "rebuild",
                "--edition",
                "0.1",
                "--work",
                str(args.work),
                "--only",
                str(args.catalog_id),
            ],
            args.output / "rebuild.log",
        )
    finally:
        monitor.stop()

    build_wall_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
    if returncode:
        raise RuntimeError(f"Decision Index rebuild exited with {returncode}")

    normalized_source = args.work / "artifacts/benchmark-suite/normalized"
    files = sorted(normalized_source.glob("*.jsonl"))
    if not files:
        raise RuntimeError("Decision Index rebuild produced no normalized files")

    normalized_output = args.output / "normalized"
    normalized_output.mkdir(parents=True, exist_ok=True)

    manifest_files = []
    for source in files:
        target = normalized_output / source.name
        shutil.copy2(source, target)
        manifest_files.append(
            {
                "name": target.name,
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )

    after = shutil.disk_usage("/")
    manifest = {
        "stack": stack,
        "kind": "decision-index-base-normalized-shard",
        "catalog_id": args.catalog_id,
        "build_edition": "0.1",
        "build_wall_ms": build_wall_ms,
        "normalized_files": manifest_files,
        "normalized_bytes": sum(item["bytes"] for item in manifest_files),
        "work_tree_bytes": tree_size(args.work),
        "disk": {
            "root_total_bytes": before.total,
            "used_before_bytes": before.used,
            "used_after_bytes": after.used,
            "peak_used_bytes": monitor.peak_used,
            "peak_increment_bytes": max(0, monitor.peak_used - before.used),
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
