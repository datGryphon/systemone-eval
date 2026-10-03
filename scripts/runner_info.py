#!/usr/bin/env python3
import json
import os
import platform
import shutil
import sys
from pathlib import Path


def cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def memory_total_kib() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1])
    except OSError:
        pass
    return None


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: runner_info.py OUTPUT.json")

    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage("/")

    payload = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": cpu_model(),
        "logical_cpus": os.cpu_count(),
        "memory_total_kib": memory_total_kib(),
        "root_disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        },
    }
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
