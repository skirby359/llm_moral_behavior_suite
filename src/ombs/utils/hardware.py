"""Capture reproducibility metadata (model list, GPU, Python, deps).

Output is written to ``outputs/<run_id>/hardware.txt``. Each probe is best-effort
and never raises — a missing tool yields a recorded "<command> unavailable" note
rather than failing the run.
"""

from __future__ import annotations

import subprocess
import sys


def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        return (out.stdout or out.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"<{' '.join(cmd)} unavailable: {exc}>"


def collect_hardware_report() -> str:
    sections = {
        "python_version": sys.version.replace("\n", " "),
        "ollama_list": _run(["ollama", "list"]),
        "nvidia_smi": _run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv"]
        ),
        "pip_freeze": _run([sys.executable, "-m", "pip", "freeze"]),
    }
    parts = []
    for title, body in sections.items():
        parts.append(f"### {title}\n{body}\n")
    return "\n".join(parts)
