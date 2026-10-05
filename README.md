# systemone-eval

CPU benchmarking for local decision models served by llama.cpp's `/v1/systemone`
endpoint and scored with Decision Index.

The benchmark records:

- Decision Index score and coverage
- request latency
- loaded-idle llama-server RSS
- peak llama-server RSS

## Manual benchmarks

Use **Actions → Benchmark model → Run workflow** to run a model against the
published canonical suite.

A run can use a saved profile from `models.json`, or an ad-hoc Hugging Face GGUF
repo with a quant and result label. The workflow also exposes shard count,
parallelism, context size, batch size, physical batch size, and extra
`llama-server` arguments.

Manual runs do not rebuild the Decision Index suite. Results are stored under:

```text
benchmarks/<github-run-id>/<label>/
```

## CI

[CI](.github/workflows/ci.yml) rebuilds and verifies the pinned Decision Index suite,
runs the Julia-1 Q8 baseline, and scores the combined results on pull requests and
pushes to `main`.

## Configuration

- `models.json`: saved model profiles and default shard counts
- `stack.json`: pinned llama.cpp revision, Decision Index revision, and edition

See [`.github/PIPELINE.md`](.github/PIPELINE.md) for the pipeline and storage layout.
