#!/usr/bin/env python3
import argparse
from dataclasses import asdict, replace
import json
import re
import shlex
from pathlib import Path

from systemone_runtime import ModelProfile, load_profile


def replace_option(args: tuple[str, ...], flag: str, value: int) -> tuple[str, ...]:
    out: list[str] = []
    index = 0
    while index < len(args):
        if args[index] == flag:
            index += 2
            continue
        out.append(args[index])
        index += 1
    out.extend((flag, str(value)))
    return tuple(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--profile", default="")
    parser.add_argument("--label", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--quant", default="")
    parser.add_argument("--shards", type=int, default=0)
    parser.add_argument("--ctx-size", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--ubatch-size", type=int, default=0)
    parser.add_argument("--extra-server-args", default="")
    parser.add_argument("--github-output", required=True, type=Path)
    args = parser.parse_args()

    if args.repo:
        if not args.quant:
            parser.error("--quant is required with --repo")
        model = ModelProfile(repo=args.repo, quant=args.quant, shards=args.shards or 32)
    elif args.profile:
        model = load_profile(args.models, args.profile)
        if args.quant:
            model = replace(model, quant=args.quant)
    else:
        parser.error("a preset --profile or ad-hoc --repo and --quant are required")

    if args.shards:
        if args.shards < 1:
            parser.error("--shards must be positive")
        model = replace(model, shards=args.shards)

    server_args = model.server_args
    for flag, value in (
        ("--ctx-size", args.ctx_size),
        ("--batch-size", args.batch_size),
        ("--ubatch-size", args.ubatch_size),
    ):
        if value:
            if value < 1:
                parser.error(f"{flag} must be positive")
            server_args = replace_option(server_args, flag, value)

    if args.extra_server_args:
        server_args += tuple(shlex.split(args.extra_server_args))
    model = replace(model, server_args=server_args)

    label = args.label or (args.profile if not args.repo else "")
    if not label:
        parser.error("--label is required with --repo")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", label):
        parser.error("--label may contain only letters, numbers, '.', '_', and '-'")

    if not 2 <= model.shards <= 512:
        parser.error("--shards must be between 2 and 512")

    split = (model.shards + 1) // 2
    matrix_a = {
        "include": [
            {"profile": label, "shard": shard, "shards": model.shards}
            for shard in range(split)
        ]
    }
    matrix_b = {
        "include": [
            {"profile": label, "shard": shard, "shards": model.shards}
            for shard in range(split, model.shards)
        ]
    }
    models = {label: asdict(model)}

    with args.github_output.open("a") as output:
        print(f"profile={label}", file=output)
        print(f"shards={model.shards}", file=output)
        print(
            "matrix-a=" + json.dumps(matrix_a, separators=(",", ":")),
            file=output,
        )
        print(
            "matrix-b=" + json.dumps(matrix_b, separators=(",", ":")),
            file=output,
        )
        print(
            "models=" + json.dumps(models, separators=(",", ":")),
            file=output,
        )

    print(json.dumps({"profile": label, "model": asdict(model)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
