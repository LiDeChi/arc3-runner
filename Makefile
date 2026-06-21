.PHONY: install api web dev test lint build

install:
	uv sync --extra dev
	cd web && npm install

api:
	uv run uvicorn server.main:app --reload --host 127.0.0.1 --port 8010

web:
	cd web && npm run dev

dev:
	@trap 'kill 0' INT TERM EXIT; \
	uv run uvicorn server.main:app --host 127.0.0.1 --port 8010 & \
	cd web && npm run dev

test:
	uv run pytest

lint:
	uv run ruff check server tests
	cd web && npm run lint

build:
	cd web && npm run build
