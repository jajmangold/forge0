FROM docker.io/library/node:22.17.0-bookworm-slim@sha256:b04ce4ae4e95b522112c2e5c52f781471a5cbc3b594527bcddedee9bc48c03a0 AS node
FROM docker.io/library/docker:27.5.1-cli@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c AS docker_cli
FROM docker.io/library/python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28

ARG CI_IMAGE_VERSION=py312-20260716

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git libatomic1 openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

COPY requirements.txt requirements-dev.txt /tmp/forge0-requirements/
RUN pip install --no-cache-dir \
      -r /tmp/forge0-requirements/requirements.txt \
      -r /tmp/forge0-requirements/requirements-dev.txt \
    && rm -rf /tmp/forge0-requirements \
    && python --version \
    && node --version \
    && pytest --version \
    && ruff --version \
    && pyright --version \
    && docker compose version

LABEL org.opencontainers.image.title="Forge0 CI base" \
      org.opencontainers.image.version="${CI_IMAGE_VERSION}" \
      org.opencontainers.image.description="Pinned, prebuilt Forge0 validation toolchain"

WORKDIR /workspace
