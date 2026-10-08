# Foundation targets never provision cloud infrastructure or claim a release gate.
PYTHON ?= python
export PYTHONPATH := backend/src:.
.PHONY: setup resolve dev api test contracts comments docs foundation lint evidence deploy

# Reproduce the committed locks. Normal setup must never silently re-resolve them.
# The resolver version used for qualification is uv 0.10.0; see the evidence index.
setup:
	uv python install 3.12.15
	uv sync --locked --no-build --group test --group quality --python 3.12.15
	cd apps/web && npm ci

# Dependency changes are deliberate maintenance work, followed by diff review and CI.
resolve:
	uv lock --python 3.12.15 --no-build
	cd apps/web && npm install --package-lock-only --ignore-scripts

# Docker is mandatory for the full local topology; there is no SQLite substitute.
dev:
	docker compose up --build

api:
	$(PYTHON) -m uvicorn matchdesk.api.app:app --host 127.0.0.1 --port 8000

test:
	$(PYTHON) -m pytest --cov=matchdesk --cov-report=term-missing

contracts:
	$(PYTHON) -m scripts.export_contracts

comments:
	$(PYTHON) -m scripts.check_comments

docs:
	$(PYTHON) -m scripts.check_docs

foundation: contracts comments docs test

# Missing linters are a failure, not an implicit waiver of the quality gate.
lint:
	ruff check backend scripts
	ruff format --check backend scripts
	mypy backend/src/matchdesk
	cd apps/web && npm run typecheck

evidence:
	$(PYTHON) -m scripts.collect_evidence

# Later phases supply reviewed Bicep and OIDC configuration. Keep this fail-closed.
deploy:
	@echo "BLOCKED: deployment implementation, resource approval and release gates are outstanding."
	@exit 2
