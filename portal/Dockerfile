FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28 AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
COPY requirements-dev.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libatomic1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

FROM dependencies AS test
COPY app/ app/
COPY tests/ tests/
COPY pytest.ini .
CMD ["pytest", "-q", "tests"]

FROM dependencies AS runtime
COPY app/ app/

RUN useradd --create-home --uid 10001 forge0 \
    && mkdir -p /var/lib/forge0/runs /var/lib/forge0/workspaces \
    && chown -R forge0:forge0 /app /var/lib/forge0
USER forge0

EXPOSE 3001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
