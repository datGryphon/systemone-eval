#!/usr/bin/env python3
from dataclasses import dataclass
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


@dataclass(frozen=True)
class ModelProfile:
    repo: str
    quant: str
    shards: int
    server_args: tuple[str, ...] = ()


def get_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def process_memory_kib(pid: int) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        key, _, rest = line.partition(":")
        if key in {"VmRSS", "VmHWM"}:
            values[key] = int(rest.split()[0])
    return values


def load_profile(path: Path, name: str) -> ModelProfile:
    profiles = json.loads(path.read_text())
    try:
        raw = profiles[name]
    except KeyError as exc:
        raise ValueError(f"unknown model profile: {name}") from exc

    try:
        repo = raw["repo"]
        quant = raw["quant"]
        shards = raw["shards"]
    except KeyError as exc:
        raise ValueError(
            f"model profile {name!r} must contain repo, quant, and shards"
        ) from exc

    server_args = raw.get("server_args", [])
    if not isinstance(shards, int) or shards < 1:
        raise ValueError(f"model profile {name!r} shards must be a positive integer")
    if not isinstance(server_args, list) or not all(
        isinstance(arg, str) for arg in server_args
    ):
        raise ValueError(f"model profile {name!r} server_args must be a list of strings")

    return ModelProfile(
        repo=str(repo),
        quant=str(quant),
        shards=shards,
        server_args=tuple(server_args),
    )


class SystemOneServer:
    def __init__(
        self,
        server: Path,
        profile: ModelProfile,
        output_dir: Path,
        port: int = 8080,
        startup_timeout: float = 180.0,
    ):
        self.server = server
        self.profile = profile
        self.output_dir = output_dir
        self.port = port
        self.startup_timeout = startup_timeout
        self.base_url = f"http://127.0.0.1:{port}"
        self.log_path = output_dir / "llama-server.log"
        self.process: subprocess.Popen | None = None
        self.loaded_memory: dict[str, int] | None = None
        self._log_handle = None

    def start(self) -> "SystemOneServer":
        self.output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.server),
            "-hf",
            f"{self.profile.repo}:{self.profile.quant}",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            *self.profile.server_args,
        ]
        self._log_handle = self.log_path.open("w")
        self.process = subprocess.Popen(
            command,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + self.startup_timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"llama-server exited with code {self.process.returncode}"
                )
            try:
                get_json(f"{self.base_url}/health")
                self.loaded_memory = process_memory_kib(self.process.pid)
                return self
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(0.5)
        raise TimeoutError(f"llama-server did not become ready: {last_error}")

    def memory(self) -> dict[str, int]:
        if not self.process:
            raise RuntimeError("server not started")
        return process_memory_kib(self.process.pid)

    def stop(self) -> None:
        if not self.process:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        if self._log_handle:
            self._log_handle.close()

    def __enter__(self) -> "SystemOneServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
