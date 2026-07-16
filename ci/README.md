# Forge0 CI base image

Pipeline jobs run in `forge0-ci-base:py312-20260716`. The image is built once
during operator setup from digest-pinned official Python, Node, and Docker CLI
images. Python dependencies are installed into the image, never during jobs.

Setup resolves the built tag to its content digest and stores that immutable
digest in the runner registration. The runner has `force_pull: false` and
`force_rebuild: false`. Job containers do not receive the Docker socket; the
bundled Docker CLI is only used for `docker compose config` validation.

Rebuild deliberately after changing `ci/Dockerfile` or either requirements file:

```bash
docker build --pull=false -f ci/Dockerfile \
  -t forge0-ci-base:py312-20260716 portal
```

After verification, change the versioned tag in `setup.sh` and this document.
Never reuse or overwrite an existing CI image tag.
