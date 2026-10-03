#!/usr/bin/env python3
import argparse
import json
import os

from huggingface_hub import HfApi, get_hf_file_metadata, hf_hub_url

from decision_index.suite.build.acquire import HF


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is required")

    api = HfApi(token=token)
    destination = api.repo_info(repo_id=args.repo, repo_type="dataset")
    if not destination.private:
        raise SystemExit(
            f"Refusing to publish Decision Index artifacts to public dataset {args.repo}"
        )

    hle_repo, hle_revision, patterns = HF["raw/hle"]
    if len(patterns) != 1 or "*" in patterns[0]:
        raise RuntimeError(f"unexpected pinned HLE file patterns: {patterns}")
    hle_file = patterns[0]
    metadata = get_hf_file_metadata(
        hf_hub_url(
            hle_repo,
            hle_file,
            repo_type="dataset",
            revision=hle_revision,
        ),
        token=token,
    )

    result = {
        "destination": {
            "repo": args.repo,
            "private": destination.private,
        },
        "gated_source_check": {
            "repo": hle_repo,
            "revision": hle_revision,
            "file": hle_file,
            "size": metadata.size,
        },
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
