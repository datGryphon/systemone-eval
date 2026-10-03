# systemone-eval

Reproducible CPU evaluation of local decision models through llama.cpp's native
`/v1/systemone` API.

The project deliberately composes existing tools rather than owning a benchmark
framework:

- **llama.cpp** provides GGUF inference and `/v1/systemone`.
- **Decision Index** provides benchmark rows, validation, quality/calibration scoring,
  and the HTTP engine.
- **GitHub-hosted Ubuntu runners** provide the common CPU/RAM environment.
- A **private Hugging Face dataset repo** stores Decision Index build shards and the
  verified frozen suite.

Evaluation artifacts record request timing, loaded-idle llama-server RSS, peak
llama-server RSS, model profile, runner information, and the exact evaluation stack.

## Pinned stack

`stack.json` is the source of truth for behavior-affecting infrastructure versions:

- exact llama.cpp Git ref
- exact Decision Index Git ref
- Decision Index edition

Suite artifacts are namespaced by the Decision Index edition and Git ref. Changing
llama.cpp therefore creates a new evaluation profile without unnecessarily rebuilding
benchmark data. Evaluation results record the full stack.

`models.json` contains the model/quant profiles exercised by the workflows.

## CI

The normal PR workflow proves three contracts:

1. Julia-1 Q8 loads in the pinned llama.cpp and serves valid typed decisions.
2. The pinned Decision Index HTTP engine can evaluate that local `/v1/systemone`
   endpoint.
3. Both Decision Index build paths can be isolated:
   - a base benchmark is reduced to normalized build artifacts;
   - an added 0.2.x benchmark is reduced to its deterministic row shard.

The integration run captures loaded-idle RSS and the process high-water mark
(`VmHWM`) so peak model RAM remains comparable with quality and latency.

Benchmark rows produced by the shard smoke jobs are not uploaded as public GitHub
Actions artifacts. Only their manifests and rebuild logs are retained there.

## Private suite storage

The suite refresh workflow expects:

- Actions secret `HF_TOKEN_READ`
- Actions secret `HF_TOKEN_WRITE`
- repository variable `HF_SUITE_REPO`, set to an existing **private Hugging Face
  dataset repo** such as `owner/systemone-eval-data`

The write token must be able to write that dataset and read any gated upstream
datasets required by Decision Index.

Artifacts are stored under:

```text
decision-index/<edition>/<decision-index-git-ref>/
├── base/<builder-group>/
├── added/<catalog-id>/
└── suite/
```

## Suite refresh

`.github/workflows/suite-refresh.yml` is manual-only.

It derives the build plan from the pinned Decision Index source. Base benchmarks are
grouped by their upstream normalizer function, because several catalog IDs share one
builder and that builder requires all of its source datasets to be present together.
Each unique base builder group and each added benchmark runs in an independent
GitHub-hosted job, publishing only the reduced shard artifact to the private HF
dataset.

After all shard jobs succeed, the assembly job:

1. downloads every expected shard;
2. reconstructs the normalized base workspace;
3. freezes the base suite using upstream Decision Index code;
4. concatenates added shards in upstream canonical order;
5. verifies the upstream base and added SHA-256 values;
6. imports/verifies the complete pinned suite with Decision Index; and
7. publishes the verified frozen suite back to the private HF dataset.

A suite is not considered valid merely because every shard built successfully. The
canonical upstream hashes must match.
