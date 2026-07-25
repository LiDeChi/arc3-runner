PYTHON ?= python3

.PHONY: test dev-api arena

test:
	cd backend && $(PYTHON) -m pytest tests -v

dev-api:
	cd backend && uvicorn arc3math.api.main:app --reload --port 8321

arena:
	cd backend && $(PYTHON) -m arc3math.arena.cli --episodes 10 --source handwritten --seed 7
