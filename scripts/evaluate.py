#!/usr/bin/env python3
import argparse
from collections import Counter
from dataclasses import asdict
import json
import os
import platform
import subprocess
import time
from pathlib import Path

from systemone_runtime import SystemOneServer, load_profile


def runner_info() -> dict:
    cpu = next(
        (
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        None,
    )
    mem_total_kib = next(
        (
            int(line.split()[1])
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemTotal:")
        ),
        None,
    )
    return {
        "platform": platform.platform(),
        "cpu_model": cpu,
        "logical_cpus": len(os.sched_getaffinity(0)),
        "memory_total_kib": mem_total_kib,
    }


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
            started = time.perf_counter()
            subprocess.run(command, check=True)
            evaluation_wall_ms = (time.perf_counter() - started) * 1000

            results = [
                json.loads(line)
                for line in (run_dir / "results.jsonl").read_text().splitlines()
                if line.strip()
            ]
            statuses = Counter(row.get("status") for row in results)
            memory = server.memory()
            metrics = {
                "stack": json.loads(args.stack.read_text()),
                "model_profile": args.profile,
                "model": asdict(profile),
                "github": {
                    "sha": os.getenv("GITHUB_SHA"),
                    "run_id": os.getenv("GITHUB_RUN_ID"),
                    "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
                },
                "runner": runner_info(),
                "decision_index": {
                    "rows": len(results),
                    "statuses": dict(statuses),
                    "evaluation_wall_ms": evaluation_wall_ms,
                },
                "memory": {
                    "loaded_idle_rss_kib": server.loaded_memory.get("VmRSS"),
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
