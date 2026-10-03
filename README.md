# systemone-eval

CPU evaluation of local decision models through llama.cpp's `/v1/systemone` API.

The benchmark stack is intentionally small:

- **Decision Index** owns benchmark data, validation, scoring, and the HTTP engine.
- **llama.cpp** owns local GGUF inference.
- **GitHub Actions** provides the common CPU runner.
- **Hugging Face** stores the private frozen Decision Index suite and build shards.

`stack.json` pins the llama.cpp and Decision Index revisions used by a run.
`models.json` defines the model/quant profiles.

Evaluation artifacts record latency, runner information, loaded-idle RSS, and peak
llama-server RSS.

See [`.github/README.md`](.github/README.md) for the pipeline architecture and data
flow.
