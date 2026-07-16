"""Single-V100 worker for Forge0's bounded static experiment harnesses."""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import re
import shutil
import socket
import statistics
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Any

import optuna
from app.experiment_queue import ExperimentQueue
from app.frontier import Objective, pareto_front

DATA = Path(os.getenv("FORGE0_EXPERIMENT_DATA", "/data"))
REPOSITORY = Path(os.getenv("FORGE0_REPOSITORY", "/repository"))
WORK = Path(os.getenv("FORGE0_EXPERIMENT_WORK", "/work"))
OWNER = f"{socket.gethostname()}:{os.getpid()}"
GPU_RESOURCE = "v100"

OBJECTIVES: list[Objective] = [
    {"name": "latency_ms", "direction": "minimize"},
    {"name": "max_abs_error", "direction": "minimize"},
    {"name": "threads", "direction": "minimize"},
]

FUSED_RE = re.compile(
    r"Fused kernel:\s+(PASS|FAIL).*?Max absolute error:\s+([0-9.eE+-]+).*?"
    r"Fused kernel:\s+([0-9.]+) ms avg, effective bandwidth:\s+([0-9.]+) GB/s",
    re.DOTALL,
)


def _bounded_run(command: list[str], *, cwd: Path, timeout: int, output_limit: int) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"},
    )
    output = result.stdout[-output_limit:]
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}):\n{output}")
    return output


def _kernel_source_hash() -> str:
    source = REPOSITORY / "kernels/rrc_swiglu"
    digest = hashlib.sha256()
    for path in sorted(source.glob("*")):
        if path.is_file() and path.suffix in {".cu", ".cuh", ""}:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _compiled_kernel(output_limit: int) -> Path:
    source = REPOSITORY / "kernels/rrc_swiglu"
    if not source.is_dir():
        raise RuntimeError("static rrc_swiglu harness source is missing")
    target = WORK / "cache" / _kernel_source_hash()
    binary = target / "rrc_swiglu_test"
    if binary.exists():
        return binary
    temporary = target.with_name(target.name + ".building")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, temporary)
    _bounded_run(["make", "all"], cwd=temporary, timeout=180, output_limit=output_limit)
    temporary.rename(target)
    return binary


def _evaluate_launch(
    binary: Path,
    params: dict[str, int],
    repetitions: int,
    timeout: int,
    output_limit: int,
) -> dict[str, Any]:
    samples: list[dict[str, float]] = []
    for _ in range(repetitions):
        output = _bounded_run(
            [
                str(binary),
                "--num_rows", str(params["num_rows"]),
                "--max_row_len", str(params["max_row_len"]),
                "--iterations", str(params["iterations"]),
                "--block_size", str(params["block_size"]),
            ],
            cwd=binary.parent,
            timeout=timeout,
            output_limit=output_limit,
        )
        match = FUSED_RE.search(output)
        if match is None:
            raise RuntimeError(f"benchmark output did not match the static contract:\n{output}")
        samples.append(
            {
                "pass": 1.0 if match.group(1) == "PASS" else 0.0,
                "max_abs_error": float(match.group(2)),
                "latency_ms": float(match.group(3)),
                "bandwidth_gbps": float(match.group(4)),
            }
        )
    return {
        "feasible": all(sample["pass"] == 1.0 for sample in samples),
        "metrics": {
            "latency_ms": statistics.median(sample["latency_ms"] for sample in samples),
            "max_abs_error": max(sample["max_abs_error"] for sample in samples),
            "threads": float(params["block_size"]),
            "bandwidth_gbps": statistics.median(sample["bandwidth_gbps"] for sample in samples),
        },
        "params": params,
        "samples": samples,
    }


def run_optuna(manifest: dict[str, Any]) -> dict[str, Any]:
    budget = manifest["budget"]
    requested = manifest.get("parameters", {})
    block_sizes = requested.get("block_sizes", [32, 64, 128, 256, 512, 1024])
    if (
        not isinstance(block_sizes, list)
        or not block_sizes
        or len(block_sizes) > 32
        or any(not isinstance(value, int) or value < 32 or value > 1024 or value % 32 for value in block_sizes)
    ):
        raise ValueError("block_sizes must be at most 32 CUDA-valid integers")
    block_sizes = sorted(set(block_sizes))
    shape = {
        "num_rows": min(int(requested.get("num_rows", 128)), 8192),
        "max_row_len": min(int(requested.get("max_row_len", 2048)), 8192),
        "iterations": min(int(requested.get("iterations", 100)), 500),
    }
    if any(value <= 0 for value in shape.values()):
        raise ValueError("shape values must be positive")
    binary = _compiled_kernel(budget["max_output_bytes"])
    candidates: list[dict[str, Any]] = []
    storage = f"sqlite:///{DATA / 'optuna.sqlite3'}"
    study = optuna.create_study(
        study_name=f"{manifest['harness']}-{int(time.time())}",
        storage=storage,
        directions=["minimize", "minimize", "minimize"],
        sampler=optuna.samplers.GridSampler({"block_size": block_sizes}, seed=manifest["seed"]),
    )

    def objective(trial: optuna.Trial) -> tuple[float, float, float]:
        params = {**shape, "block_size": trial.suggest_categorical("block_size", block_sizes)}
        candidate = _evaluate_launch(
            binary,
            params,
            budget["repetitions"],
            min(120, budget["wall_seconds"]),
            budget["max_output_bytes"],
        )
        candidates.append(candidate)
        metrics = candidate["metrics"]
        trial.set_user_attr("bandwidth_gbps", metrics["bandwidth_gbps"])
        trial.set_user_attr("feasible", candidate["feasible"])
        if not candidate["feasible"]:
            return float("inf"), float("inf"), float(params["block_size"])
        return metrics["latency_ms"], metrics["max_abs_error"], metrics["threads"]

    study.optimize(objective, n_trials=min(budget["trials"], len(block_sizes)), timeout=budget["wall_seconds"])
    return {
        "method": "optuna",
        "harness": manifest["harness"],
        "study_name": study.study_name,
        "objectives": OBJECTIVES,
        "candidates": candidates,
        "frontier": pareto_front(candidates, OBJECTIVES),
        "iterations": len(candidates),
        "compile_cache": str(binary.parent.name),
    }


def run_openevolve(manifest: dict[str, Any]) -> dict[str, Any]:
    """Evolve only the reviewed cross-warp reduction block."""
    from openevolve import run_evolution
    from openevolve.config import (
        Config,
        DatabaseConfig,
        EvaluatorConfig,
        LLMConfig,
        LLMModelConfig,
        PromptConfig,
    )

    budget = manifest["budget"]
    source = (REPOSITORY / "kernels/rrc_swiglu/rrc_swiglu_kernel.cu").read_text()
    start = "__device__ float block_reduce_sum(float val, float* shared, int tid, int num_threads) {"
    end = "\n// ---------------------------------------------------------------------------\n// RRC-SwiGLU kernel"
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError("static evolution boundaries no longer match the kernel")
    source = source.replace(start, f"// EVOLVE-BLOCK-START\n{start}", 1)
    source = source.replace(end, f"// EVOLVE-BLOCK-END{end}", 1)
    evaluator_path = REPOSITORY / "experiments/harnesses/rrc_swiglu_evaluator.py"
    iterations = min(int(manifest.get("parameters", {}).get("iterations", 4)), budget["trials"])
    output_dir = DATA / "openevolve" / f"run-{int(time.time())}"
    llm_timeout = max(30, min(120, budget["wall_seconds"] // iterations - 20))
    model = LLMModelConfig(
        name=os.getenv("FORGE0_EVOLVE_MODEL", "mimo-v2.5"),
        api_base=os.environ["OPENCODE_BASE_URL"],
        api_key=os.environ["OPENCODE_API_KEY"],
        max_tokens=min(8000, budget["llm_tokens"]),
        timeout=llm_timeout,
        retries=0,
        random_seed=manifest["seed"],
    )
    config = Config(
        max_iterations=iterations,
        checkpoint_interval=iterations,
        random_seed=manifest["seed"],
        language="cuda",
        file_suffix=".cu",
        max_code_length=len(source) + 4000,
        llm=LLMConfig(models=[model], evaluator_models=[model], max_tokens=model.max_tokens),
        prompt=PromptConfig(
            system_message=(
                "Optimize only the marked CUDA block reduction. Preserve its signature, synchronization "
                "contract, numerical result, and support for block sizes 32..1024. Return a small SEARCH/REPLACE diff."
            ),
            num_top_programs=2,
            num_diverse_programs=1,
            include_artifacts=True,
        ),
        database=DatabaseConfig(
            db_path=str(output_dir / "database"),
            in_memory=False,
            population_size=4,
            archive_size=8,
            num_islands=1,
            feature_dimensions=["complexity", "latency_ms", "changed_lines"],
            feature_bins=4,
            random_seed=manifest["seed"],
        ),
        evaluator=EvaluatorConfig(
            timeout=min(120, budget["wall_seconds"]),
            max_retries=0,
            cascade_evaluation=False,
            parallel_evaluations=1,
            use_llm_feedback=False,
        ),
    )
    os.environ["FORGE0_MAX_EVOLVE_CHANGED_LINES"] = str(budget["max_changed_lines"])
    result = run_evolution(
        initial_program=source,
        evaluator=str(evaluator_path),
        iterations=iterations,
        output_dir=str(output_dir),
        cleanup=False,
        config=config,
    )
    candidates: list[dict[str, Any]] = []
    for program_file in (output_dir / "database/programs").glob("*.json"):
        program = json.loads(program_file.read_text())
        metrics = program.get("metrics", {})
        if all(name in metrics for name in ("latency_ms", "max_abs_error", "changed_lines")):
            candidates.append(
                {
                    "id": program.get("id"),
                    "metrics": {
                        "latency_ms": metrics["latency_ms"],
                        "max_abs_error": metrics["max_abs_error"],
                        "threads": metrics.get("threads", 256),
                        "changed_lines": metrics["changed_lines"],
                    },
                    "feasible": bool(metrics.get("correct", 0)),
                }
            )
    return {
        "method": "openevolve",
        "harness": manifest["harness"],
        "best_score": result.best_score,
        "best_metrics": result.metrics,
        "best_code": result.best_code,
        "objectives": OBJECTIVES,
        "candidates": candidates,
        "frontier": pareto_front(candidates, OBJECTIVES),
        "iterations": iterations,
        "output_dir": str(output_dir.relative_to(DATA)),
    }


def _heartbeat(queue: ExperimentQueue, job_id: str, stop: threading.Event) -> None:
    while not stop.wait(20):
        queue.heartbeat(job_id, OWNER, lease_seconds=60)


def _run_harness_child(manifest: dict[str, Any], connection: Any) -> None:
    """Execute one harness behind a killable whole-job wall clock."""
    try:
        if manifest["method"] == "optuna":
            connection.send({"result": run_optuna(manifest)})
        elif manifest["method"] == "openevolve":
            connection.send({"result": run_openevolve(manifest)})
        else:
            raise ValueError("GPU worker received a non-GPU harness")
    except Exception as exc:
        connection.send({"error": f"{exc}\n{traceback.format_exc()}"})
    finally:
        connection.close()


def _run_with_wall_limit(manifest: dict[str, Any]) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_run_harness_child, args=(manifest, child))
    process.start()
    child.close()
    wall_seconds = int(manifest["budget"]["wall_seconds"])
    try:
        if not parent.poll(wall_seconds):
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            raise TimeoutError(f"experiment exceeded its {wall_seconds}s whole-job limit")
        payload = parent.recv()
    finally:
        parent.close()
    process.join(timeout=5)
    if process.is_alive():
        process.terminate()
        process.join(timeout=2)
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload["result"]


def _track_wandb(job_id: str, manifest: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Log bounded summaries; offline mode is the durable default."""
    import wandb

    directory = DATA / "wandb"
    directory.mkdir(parents=True, exist_ok=True)
    mode = os.getenv("WANDB_MODE", "offline")
    run = wandb.init(
        project="forge0-experiments",
        id=job_id,
        name=job_id,
        dir=str(directory),
        mode=mode,
        config=manifest,
        resume="allow" if mode == "online" else None,
        reinit="finish_previous",
        tags=[manifest["method"], manifest["harness"], "bounded", "pareto"],
    )
    for index, candidate in enumerate(result.get("candidates", [])):
        metrics = candidate.get("metrics", {})
        run.log(
            {
                "candidate/index": index,
                "candidate/feasible": int(candidate.get("feasible", True)),
                **{
                    f"metric/{name}": value
                    for name, value in metrics.items()
                    if isinstance(value, int | float)
                },
            }
        )
    run.summary["frontier_size"] = len(result.get("frontier", []))
    run.summary["elapsed_seconds"] = result.get("elapsed_seconds", 0)
    run.finish()
    return {"mode": mode, "run_id": job_id}


def execute(queue: ExperimentQueue, record: Any) -> None:
    stop = threading.Event()
    heartbeat = threading.Thread(target=_heartbeat, args=(queue, record.id, stop), daemon=True)
    heartbeat.start()
    started = time.perf_counter()
    try:
        result = _run_with_wall_limit(record.manifest)
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        try:
            result["wandb"] = _track_wandb(record.id, record.manifest, result)
        except Exception as tracking_error:
            result["wandb"] = {"status": "spooled-jsonl", "error": str(tracking_error)[:500]}
        queue.finish(record.id, OWNER, result=result)
        with (DATA / "events.jsonl").open("a") as stream:
            stream.write(json.dumps({"job_id": record.id, "status": "succeeded", **result}) + "\n")
    except Exception as exc:
        queue.finish(record.id, OWNER, error=f"{exc}\n{traceback.format_exc()}")
    finally:
        stop.set()
        heartbeat.join(timeout=2)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    queue = ExperimentQueue(DATA / "experiments.sqlite3")
    while True:
        record = queue.claim(GPU_RESOURCE, OWNER, lease_seconds=60)
        if record is None:
            time.sleep(1)
            continue
        execute(queue, record)


if __name__ == "__main__":
    main()
