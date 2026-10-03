#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


SMOKE_PAYLOAD = {
    "state": "Customer message: I was charged twice for my order last week and nobody has replied.",
    "questions": {
        "route": {
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {
                "billing": None,
                "shipping": None,
                "technical": None,
            },
        },
        "angry": {
            "type": "noul",
            "instructions": "Is the customer angry?",
        },
        "urgency": {
            "type": "score",
            "instructions": "How urgent is this?",
            "criteria": ["can wait", "this week", "today", "right now"],
        },
    },
}


def request_json(url: str, payload: dict | None = None, timeout: float = 5.0) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    headers = {} if payload is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def process_memory_kib(pid: int) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        key, _, rest = line.partition(":")
        if key in {"VmRSS", "VmHWM"}:
            values[key] = int(rest.split()[0])
    return values


def wait_until_ready(process: subprocess.Popen, base_url: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited with code {process.returncode}")
        try:
            return request_json(f"{base_url}/health")
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(f"llama-server did not become ready: {last_error}")


def validate_response(response: dict) -> None:
    answers = response["answers"]
    route = answers["route"]["probabilities"]
    urgency = answers["urgency"]["probabilities"]

    if set(route) != {"billing", "shipping", "technical"}:
        raise ValueError(f"unexpected route distribution: {route}")
    if len(urgency) != 4:
        raise ValueError(f"unexpected urgency distribution: {urgency}")
    if not isinstance(answers["angry"]["noul"], (int, float)):
        raise ValueError("noul response is not numeric")
    if response.get("usage", {}).get("output_tokens") != 0:
        raise ValueError("System One response generated output tokens")


def load_profile(path: Path, name: str) -> dict[str, str]:
    profiles = json.loads(path.read_text())
    try:
        profile = profiles[name]
    except KeyError as exc:
        raise SystemExit(f"unknown model profile: {name}") from exc
    if set(profile) != {"repo", "quant"}:
        raise SystemExit(f"model profile {name!r} must contain exactly repo and quant")
    return profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--startup-timeout", type=float, default=180.0)
    args = parser.parse_args()

    profile = load_profile(args.models, args.profile)
    args.output.mkdir(parents=True, exist_ok=True)
    log_path = args.output / "llama-server.log"
    base_url = f"http://127.0.0.1:{args.port}"

    command = [
        str(args.server),
        "-hf",
        f"{profile['repo']}:{profile['quant']}",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]

    with log_path.open("w") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            text=True,
        )

    try:
        health = wait_until_ready(process, base_url, args.startup_timeout)
        loaded_memory = process_memory_kib(process.pid)

        started_ns = time.perf_counter_ns()
        response = request_json(
            f"{base_url}/v1/systemone",
            SMOKE_PAYLOAD,
            timeout=120.0,
        )
        request_wall_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        validate_response(response)

        post_request_memory = process_memory_kib(process.pid)
        metrics = {
            "model_profile": args.profile,
            "model": profile,
            "server_pid": process.pid,
            "memory": {
                "loaded_idle_rss_kib": loaded_memory.get("VmRSS"),
                "post_request_rss_kib": post_request_memory.get("VmRSS"),
                "process_peak_rss_kib": post_request_memory.get("VmHWM"),
            },
            "smoke_request_wall_ms": request_wall_ms,
        }

        (args.output / "health.json").write_text(json.dumps(health, indent=2) + "\n")
        (args.output / "response.json").write_text(json.dumps(response, indent=2) + "\n")
        (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        print(json.dumps(metrics, indent=2))
    except Exception:
        if log_path.exists():
            print(log_path.read_text()[-12000:])
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
