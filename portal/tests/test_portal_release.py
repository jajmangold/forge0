from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_portal_release_uses_immutable_canary_and_no_build_promotion() -> None:
    script = (ROOT / "scripts/release-portal.sh").read_text()
    compose = (ROOT / "docker-compose.yaml").read_text()

    assert "docker image inspect --format '{{.Id}}'" in script
    assert 'docker image inspect "$tag"' in script
    assert "docker build --provenance=false" in script
    assert "FORGE0_SUPERVISOR_ENABLED=false" in script
    assert 'wait_ready "http://localhost:${CANARY_PORT}"' in script
    assert "--no-build portal" in script
    assert "promote \"$previous_image\"" in script
    assert "${FORGE0_PORTAL_IMAGE:-forge0-portal:current}" in compose
    assert 'docker tag "$image" forge0-portal:current' in script


def test_portal_release_state_is_outside_the_repository_history() -> None:
    script = (ROOT / "scripts/release-portal.sh").read_text()

    assert ".forge0-runtime/releases" in script
    assert "previous.env" in script
    assert "current.env" in script
