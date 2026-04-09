# Dockerfile for py-dss-service
# ------------------------------

# Base stage – installs Python runtime and project dependencies
FROM python:3.12-slim AS base

WORKDIR /app

# Copy the minimal files needed to install the package
COPY README.md .
COPY pyproject.toml .
COPY src/ src/

# Install the runtime package (editable for dev, wheel for prod)
RUN pip install --no-cache-dir -e . \
    && rm -rf /root/.cache

# API stage – default command is the FastAPI server
FROM base AS api
CMD ["python", "-m", "py_dss_service.api.main"]

# Worker stage – runs the task queue worker
FROM base AS worker
CMD ["python", "-m", "py_dss_service.worker.main"]

# Dev stage – add dev packages
FROM base AS dev
RUN pip install --no-cache-dir .[dev] \
    && rm -rf /root/.cache

# Lint stage - run linter
FROM dev AS lint
COPY docker/lint.sh /lint.sh
RUN chmod +x /lint.sh
ENTRYPOINT ["/lint.sh"]

FROM dev AS test
COPY tests/ tests/
CMD ["python", "-m", "pytest", "tests", "-q"]
