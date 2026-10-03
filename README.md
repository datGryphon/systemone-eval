# systemone-eval

Reproducible CPU evaluation of local decision models through llama.cpp's native
`/v1/systemone` API.

The project composes upstream tools rather than owning a benchmark framework:

- **llama.cpp** provides GGUF inference and `/v1/systemone`.
- **Decision Index** provides benchmark acquisition, normalization, frozen-suite
  validation, quality/calibration scoring, and the HTTP engine.
- **Hugging Face's `hf` CLI** stores and retrieves private suite shards.
- **GitHub-hosted Ubuntu runners** provide the common CPU/RAM environment.

Evaluation artifacts record request timing, loaded-idle llama-server RSS, peak
llama-server RSS, model profile, runner information, and the exact evaluation stack.

## Pinned stack

`stack.json` is the source of truth for behavior-affecting infrastructure versions:

- exact llama.cpp Git ref
- exact Decision Index Git ref
- Decision Index edition

Suite artifacts are namespaced by the Decision Index edition and Git ref. Evaluation
results record the full stack.

## CI

Normal PR CI proves:

1. Julia-1 Q8 loads in the pinned llama.cpp and serves typed decisions.
2. The pinned Decision Index HTTP engine can evaluate that local endpoint.
3. A shared Decision Index base normalizer can be rebuilt with all catalog IDs it
   requires.
4. An added 0.2.x benchmark can be rebuilt independently.
5. On same-repository PRs, both shard types round-trip through the private Hugging
   Face dataset using the upstream `hf upload` and `hf download` commands.

No benchmark rows are published as GitHub Actions artifacts.

The integration run captures loaded-idle RSS and the llama-server process high-water
mark (`VmHWM`) so peak RAM remains comparable with quality and latency.

## Private suite storage

The workflows expect:

- Actions secret `HF_TOKEN_READ`
- Actions secret `HF_TOKEN_WRITE`
- repository variable `HF_SUITE_REPO` pointing to an existing private dataset repo

Artifacts live under:

```text
decision-index/<edition>/<decision-index-git-ref>/
├── base/<builder-group>/normalized/
├── added/<catalog-id>/added-rows.jsonl
└── suite/
```

## Suite refresh

`.github/workflows/suite-refresh.yml` is manual-only.

The plan is derived directly from the pinned Decision Index source. Base catalog IDs
that share one upstream normalizer are rebuilt together; added benchmarks are rebuilt
independently. Each job runs Decision Index's own `suite rebuild` command and sends
only its reduced output to the private dataset with `hf upload`.

After all shards exist, the assembly job uses `hf download`, stages the files into
the layout Decision Index expects, and then delegates the canonical work back to
Decision Index:

1. `suite rebuild --skip-download --skip-normalize` recreates the frozen base rows;
2. added shards are concatenated in Decision Index's published `ORDER`;
3. `suite import` enforces the edition's canonical hashes;
4. `suite verify` verifies the completed suite; and
5. `hf upload` publishes that verified suite.

The only project-owned suite glue is the small planner/stager needed because Decision
Index does not currently expose shared-builder sharding or recombination as CLI
commands.
