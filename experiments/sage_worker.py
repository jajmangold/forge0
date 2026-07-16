"""Networkless SageMath worker for exact, bounded expression checks."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import traceback
from pathlib import Path

from runtime_queue import RuntimeQueue

DATA = Path(os.getenv("FORGE0_EXPERIMENT_DATA", "/data"))
OWNER = f"sage:{socket.gethostname()}:{os.getpid()}"
FORBIDDEN = re.compile(r"(__|\bimport\b|\bopen\b|\bexec\b|\beval\b|\bos\b|\bsys\b|subprocess|socket)")


def evaluate(manifest: dict) -> dict:
    expression = str(manifest["parameters"]["expression"])
    if FORBIDDEN.search(expression):
        raise ValueError("expression contains a forbidden capability")
    budget = manifest["budget"]
    encoded_expression = json.dumps(expression)
    expected = manifest["parameters"].get("expected")
    encoded_expected = json.dumps(str(expected)) if expected is not None else "None"
    script = (
        "from sage.all import *; x,y,z=var('x y z'); "
        f"v=sage_eval({encoded_expression},locals={{'x':x,'y':y,'z':z}}); "
        f"expected_source={encoded_expected}; "
        "e=sage_eval(expected_source,locals={'x':x,'y':y,'z':z}) if expected_source is not None else None; "
        "matches=True if e is None else bool(v == e or (hasattr(v,'simplify_full') and (v-e).simplify_full() == 0)); "
        "print(json.dumps({'value':str(v),'latex':latex(v),'type':str(type(v)),'matches_expected':matches}))"
    )
    result = subprocess.run(
        ["sage", "-python", "-c", "import json; " + script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=min(120, budget["wall_seconds"]),
        check=False,
    )
    output = result.stdout[-budget["max_output_bytes"] :]
    if result.returncode:
        raise RuntimeError(output)
    payload = json.loads(output.strip().splitlines()[-1])
    return {"method": "sage", "harness": manifest["harness"], "result": payload}


def main() -> None:
    queue = RuntimeQueue(DATA / "experiments.sqlite3")
    while True:
        record = queue.claim("sage", OWNER, lease_seconds=180)
        if record is None:
            time.sleep(1)
            continue
        started = time.perf_counter()
        try:
            result = evaluate(record.manifest)
            result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            queue.finish(record.id, OWNER, result=result)
        except Exception as exc:
            queue.finish(record.id, OWNER, error=f"{exc}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
