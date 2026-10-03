#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

REQUIRED = {
    "llama_cpp": {"repository", "ref"},
    "decision_index": {"repository", "ref", "edition"},
}

def load_stack(path: Path) -> dict:
    stack = json.loads(path.read_text())
    if stack.get("schema_version") != 1:
        raise ValueError("unsupported stack schema_version")
    for section, keys in REQUIRED.items():
        value = stack.get(section)
        if not isinstance(value, dict):
            raise ValueError(f"missing stack section: {section}")
        missing = keys - value.keys()
        if missing:
            raise ValueError(f"{section} missing keys: {sorted(missing)}")
    return stack

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stack", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    stack = load_stack(args.stack)
    if args.github_output:
        values = {
            "llama-cpp-ref": stack["llama_cpp"]["ref"],
            "decision-index-ref": stack["decision_index"]["ref"],
            "decision-index-edition": stack["decision_index"]["edition"],
        }
        with args.github_output.open("a") as output:
            for key, value in values.items():
                print(f"{key}={value}", file=output)
    else:
        print(json.dumps(stack, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
