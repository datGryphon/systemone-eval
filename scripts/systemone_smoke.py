#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path

from stack_config import load_stack
from systemone_runtime import SystemOneServer, load_profile, request_json

SMOKE_PAYLOAD = {
    "state": "Customer message: I was charged twice for my order last week and nobody has replied.",
    "questions": {
        "route": {
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {"billing": None, "shipping": None, "technical": None},
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

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--stack", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    profile = load_profile(args.models, args.profile)
    stack = load_stack(args.stack)
    try:
        with SystemOneServer(args.server, profile, args.output) as server:
            started_ns = time.perf_counter_ns()
            response = request_json(f"{server.base_url}/v1/systemone", SMOKE_PAYLOAD, timeout=120.0)
            request_wall_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            validate_response(response)
            memory = server.memory()
            metrics = {
                "stack": stack,
                "model_profile": args.profile,
                "model": profile,
                "memory": {
                    "loaded_idle_rss_kib": server.loaded_memory.get("VmRSS"),
                    "post_request_rss_kib": memory.get("VmRSS"),
                    "process_peak_rss_kib": memory.get("VmHWM"),
                },
                "smoke_request_wall_ms": request_wall_ms,
            }
            (args.output / "response.json").write_text(json.dumps(response, indent=2) + "\n")
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
