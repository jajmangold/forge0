"""Static OpenEvolve evaluator for the marked CUDA block reduction only."""
from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from openevolve.evaluation_result import EvaluationResult

REPOSITORY = Path(os.environ.get("FORGE0_REPOSITORY", "/repository"))
BASE = REPOSITORY / "kernels/rrc_swiglu"
START = "__device__ float block_reduce_sum(float val, float* shared, int tid, int num_threads) {"
END = "\n// ---------------------------------------------------------------------------\n// RRC-SwiGLU kernel"
OUTPUT_RE = re.compile(
    r"Fused kernel:\s+(PASS|FAIL).*?Max absolute error:\s+([0-9.eE+-]+).*?"
    r"Fused kernel:\s+([0-9.]+) ms avg, effective bandwidth:\s+([0-9.]+) GB/s",
    re.DOTALL,
)


def _parts(source: str) -> tuple[str, str, str]:
    clean = source.replace("// EVOLVE-BLOCK-START\n", "").replace("// EVOLVE-BLOCK-END", "")
    before, remainder = clean.split(START, 1)
    body, after = remainder.split(END, 1)
    return before, START + body, END + after


def _failure(message: str) -> EvaluationResult:
    return EvaluationResult(
        metrics={
            "combined_score": 0.0,
            "correct": 0.0,
            "latency_ms": 1_000_000.0,
            "max_abs_error": 1_000_000.0,
            "changed_lines": 1_000_000.0,
            "threads": 256.0,
        },
        artifacts={"failure": message[-12000:]},
    )


def evaluate(program_path: str) -> EvaluationResult:
    candidate = Path(program_path).read_text()
    baseline = (BASE / "rrc_swiglu_kernel.cu").read_text()
    try:
        candidate_before, candidate_body, candidate_after = _parts(candidate)
        baseline_before, baseline_body, baseline_after = _parts(baseline)
    except ValueError as exc:
        return _failure(f"mutation boundaries were damaged: {exc}")
    if candidate_before != baseline_before or candidate_after != baseline_after:
        return _failure("candidate changed code outside the reviewed reduction block")

    diff = list(difflib.unified_diff(baseline_body.splitlines(), candidate_body.splitlines()))
    changed_lines = sum(line.startswith(("+", "-")) and not line.startswith(("+++", "---")) for line in diff)
    limit = int(os.environ.get("FORGE0_MAX_EVOLVE_CHANGED_LINES", "60"))
    if changed_lines > limit:
        return _failure(f"candidate changed {changed_lines} lines; limit is {limit}")

    with tempfile.TemporaryDirectory(prefix="forge0-evolve-") as temporary:
        work = Path(temporary)
        for name in ("Makefile", "rrc_swiglu.cuh", "rrc_swiglu_test.cu"):
            shutil.copy2(BASE / name, work / name)
        (work / "rrc_swiglu_kernel.cu").write_text(
            candidate.replace("// EVOLVE-BLOCK-START\n", "").replace("// EVOLVE-BLOCK-END", "")
        )
        environment = {**os.environ, "CUDA_VISIBLE_DEVICES": "0"}
        build = subprocess.run(
            ["make", "all"], cwd=work, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90, check=False,
        )
        if build.returncode:
            return _failure("compile failed:\n" + build.stdout)
        outputs: list[str] = []
        for block_size in (32, 256, 1024):
            run = subprocess.run(
                [
                    str(work / "rrc_swiglu_test"), "--num_rows", "128", "--max_row_len", "2048",
                    "--iterations", "50", "--block_size", str(block_size),
                ],
                cwd=work, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False,
            )
            if run.returncode:
                return _failure(f"block {block_size} failed:\n{run.stdout}")
            outputs.append(run.stdout)

    parsed = [OUTPUT_RE.search(output) for output in outputs]
    if any(match is None for match in parsed):
        return _failure("benchmark output violated the static parser contract")
    matches = [match for match in parsed if match is not None]
    correct = all(match.group(1) == "PASS" for match in matches)
    max_error = max(float(match.group(2)) for match in matches)
    latency = float(matches[1].group(3))
    bandwidth = float(matches[1].group(4))
    feasible = correct and max_error <= 1e-4 and latency > 0
    return EvaluationResult(
        metrics={
            "combined_score": 1.0 / latency if feasible else 0.0,
            "correct": 1.0 if feasible else 0.0,
            "latency_ms": latency,
            "max_abs_error": max_error,
            "bandwidth_gbps": bandwidth,
            "changed_lines": float(changed_lines),
            "threads": 256.0,
        },
        artifacts={"benchmark_tail": "\n".join(output[-3000:] for output in outputs)},
    )
