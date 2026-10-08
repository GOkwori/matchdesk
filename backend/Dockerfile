# Local foundation only; image digests and vulnerability scans are release gates.
FROM ghcr.io/astral-sh/uv:0.10.0 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend/src
# Missing lockfiles deliberately fail the build rather than resolve drifting dependencies.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/src backend/src
RUN useradd --uid 10001 --create-home matchdesk
USER 10001
EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "matchdesk.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
