# systemone-eval

Reproducible CPU evaluation of local decision models through llama.cpp's native
`/v1/systemone` API.

The initial stack is intentionally small:

- llama.cpp provides GGUF inference and the System One API.
- Decision Index will provide the common quality/calibration harness.
- GitHub-hosted Linux runners provide the common CPU/RAM environment.
- A private Hugging Face dataset repository will hold frozen benchmark artifacts.
- Evaluation records include latency, loaded-idle RSS, and peak llama-server RSS.

## Current milestone

The bootstrap workflow proves that a pinned llama.cpp revision can load Julia-1 Q8 on
a standard GitHub-hosted CPU runner and return valid `choice`, `noul`, and `score`
probability outputs from `/v1/systemone`.

The workflow records:

- GitHub runner CPU/RAM/disk information
- pinned llama.cpp revision
- model repository and quant
- llama-server loaded-idle RSS
- llama-server process peak RSS
- one System One request wall time
- raw response and server log

Decision Index integration comes after this inference path is verified.
