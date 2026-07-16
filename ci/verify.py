"""Static invariants for the no-churn Forge0 Actions pipeline."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".gitea" / "workflows").glob("*.yaml"))


def main() -> None:
    """Reject mutable actions, runtime installs, builds, and non-CI labels."""
    forbidden = ("docker build", "docker compose build", "pip install", "actions/setup-python@")
    action_pattern = re.compile(r"uses:\s*[^\s@]+@([^\s]+)")

    for workflow in WORKFLOWS:
        text = workflow.read_text()
        lowered = text.lower()
        for command in forbidden:
            assert command not in lowered, f"{workflow}: forbidden runtime churn: {command}"
        for reference in action_pattern.findall(text):
            assert re.fullmatch(r"[0-9a-f]{40}", reference), (
                f"{workflow}: action reference must be a full commit SHA: {reference}"
            )
        document = yaml.safe_load(text)
        for name, job in document.get("jobs", {}).items():
            assert job.get("runs-on") == "forge0-ci", f"{workflow}:{name} must use forge0-ci"

    dockerfile = (ROOT / "ci" / "Dockerfile").read_text()
    from_lines = [line for line in dockerfile.splitlines() if line.startswith("FROM ")]
    assert from_lines and all("@sha256:" in line for line in from_lines), "Every CI base must be digest-pinned"

    runner = yaml.safe_load((ROOT / "runner" / "config.yaml").read_text())
    container = runner["container"]
    assert container["docker_host"] == "-", "Job containers must not receive the Docker socket"
    assert container["force_pull"] is False
    assert container["force_rebuild"] is False

    print(f"Verified {len(WORKFLOWS)} no-churn workflows.")


if __name__ == "__main__":
    main()
