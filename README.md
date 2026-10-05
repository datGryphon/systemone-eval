# systemone-eval

Reproducible CPU benchmarking for local decision models exposed through
llama.cpp's `/v1/systemone` API.

The project compares:

- Decision Index quality
- CPU inference latency
- loaded-idle RAM
- peak llama-server RAM

`models.json` defines the model/quant profiles under test. `stack.json` pins the
llama.cpp and Decision Index revisions used for a run.

Pull requests and `main` both run the complete data-build and evaluation pipeline.
For pipeline architecture, private artifact storage, and cleanup behavior, see
[`.github/README.md`](.github/README.md).
