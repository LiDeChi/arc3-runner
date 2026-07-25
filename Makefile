.PHONY: install api web dev open test test-product test-math test-world-model lint build

install:
	uv sync --extra dev
	cd web && npm ci

api:
	uv run uvicorn server.main:app --reload --host 127.0.0.1 --port 8010

web:
	cd web && npm run dev

dev:
	@trap 'kill 0' INT TERM EXIT; \
	uv run uvicorn server.main:app --host 127.0.0.1 --port 8010 & \
	cd web && npm run dev

open:
	bash scripts/open-experience.sh

test: test-product test-math test-world-model

test-product:
	uv run pytest

test-math:
	cd packages/arc3-math && ../../.venv/bin/python -m pytest -q

test-world-model:
	cd experiments/world-model && ../../.venv/bin/python -m pytest -q

lint:
	uv run ruff check server tests
	cd web && npm run lint

build:
	cd web && npm run build
