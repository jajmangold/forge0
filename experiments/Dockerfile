FROM nvidia/cuda@sha256:020bc241a628776338f4d4053fed4c38f6f7f3d7eb5919fecb8de313bb8ba47c

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/forge0/venv/bin:$PATH \
    PYTHONPATH=/opt/forge0/portal

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git make python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/forge0/venv

COPY experiments/requirements.lock /opt/forge0/requirements.lock
RUN pip install --no-cache-dir -r /opt/forge0/requirements.lock

COPY portal/app /opt/forge0/portal/app
COPY experiments/worker.py /opt/forge0/worker.py

RUN useradd --create-home --uid 10001 experiment \
    && mkdir -p /data /work \
    && chown -R experiment:experiment /data /work
USER experiment
WORKDIR /work

CMD ["python", "/opt/forge0/worker.py"]
