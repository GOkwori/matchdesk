# Immutable Alpine base selected from hosted candidate run 37778408263.
# Build and runtime use the same Python patch level; only locked app dependencies
# are copied into the final non-root service image.
FROM ghcr.io/astral-sh/uv:0.10.0@sha256:78a7ff97cd27b7124a5f3c2aefe146170793c56a1e03321dd31a289f6d82a04f AS uv
FROM python:3.12.15-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
# Pull patched Alpine packages during the controlled build, then resolve only
# the committed lock. No compiler or package manager is copied from this stage.
RUN apk upgrade --no-cache
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --no-build --python /usr/local/bin/python

FROM python:3.12.15-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend/src
RUN apk upgrade --no-cache
COPY --from=build /app/.venv /app/.venv
COPY backend/src backend/src
# The service runs locked packages from the copied venv; it never installs packages.
# Remove the base image's unused pip after the OS upgrade and assert it is absent.
RUN /usr/local/bin/python -m pip uninstall --yes pip \
    && /usr/local/bin/python -c "import importlib.util, shutil; assert importlib.util.find_spec('pip') is None; assert shutil.which('pip') is None"
RUN adduser -D -u 10001 -h /home/matchdesk matchdesk
USER 10001
EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "matchdesk.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header"]
