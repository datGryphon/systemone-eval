#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from systemone_runtime import SystemOneServer, load_profile

def read_results(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--decision-index", required=True, type=Path)
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--stack", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    profile = load_profile(args.models, args.profile)
    stack = json.loads(args.stack.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    run_dir = args.output / "decision-index"

    try:
        with SystemOneServer(args.server, profile, args.output) as server:
            command = [
                str(args.decision_index),
                "run",
                "--engine", "http",
                "--option", f"base_url={server.base_url}",
                "--option", f"model={args.profile}",
                "--rows", str(args.rows),
                "--out", str(run_dir),
                "--compact",
                "--fresh",
            ]
            started_ns = time.perf_counter_ns()
            completed = subprocess.run(command, env=os.environ.copy(), text=True, check=False)
            evaluation_wall_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            if completed.returncode:
                raise RuntimeError(f"Decision Index exited with {completed.returncode}")

            results = read_results(run_dir / "results.jsonl")
            if not results:
                raise RuntimeError("Decision Index produced no result rows")
            failures = [row for row in results if row.get("status") != "ok"]
            if failures:
                raise RuntimeError(f"Decision Index failures: {failures}")

            memory = server.memory()
            metrics = {
                "stack": stack,
                "model_profile": args.profile,
                "model": profile,
                "decision_index": {
                    "rows": len(results),
                    "statuses": {"ok": len(results)},
                    "evaluation_wall_ms": evaluation_wall_ms,
                },
                "memory": {
                    "loaded_idle_rss_kib": server.loaded_memory.get("VmRSS"),
                    "post_evaluation_rss_kib": memory.get("VmRSS"),
                    "process_peak_rss_kib": memory.get("VmHWM"),
                },
            }
            (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
            print(json.dumps(metrics, indent=2))
    except Exception:
        log_path = args.output / "llama-server.log"
        if log_path.exists():
            print(log_path.read_text()[-12000:])
        raise
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
