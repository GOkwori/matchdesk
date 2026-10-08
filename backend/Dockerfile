# Immutable inputs were resolved from their registries in run 37754604886.
# Dependency installation is isolated from the minimal, non-root runtime image.
FROM ghcr.io/astral-sh/uv:0.10.0@sha256:78a7ff97cd27b7124a5f3c2aefe146170793c56a1e03321dd31a289f6d82a04f AS uv
FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
# Reject stale locks. Test/quality tools and source builds are not runtime dependencies.
RUN uv sync --locked --no-default-groups --no-build --python /usr/local/bin/python

FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend/src
COPY --from=build /app/.venv /app/.venv
COPY backend/src backend/src
# The service runs locked packages from the copied venv; it never installs packages.
# Remove the base image's unused pip, not scanner metadata or application libraries.
# The executable absence check is executed during every runtime-image build.
RUN /usr/local/bin/python -m pip uninstall --yes pip \
    && /usr/local/bin/python -c "import importlib.util, shutil; assert importlib.util.find_spec('pip') is None; assert shutil.which('pip') is None"
RUN useradd --uid 10001 --no-log-init --create-home matchdesk
USER 10001
EXPOSE 8000
# Do not trust forwarded headers on this local foundation API.
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "matchdesk.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header"]
