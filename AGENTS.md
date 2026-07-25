# ARC3 Adversarial Training Platform

Adversarial training platform for ARC (Abstraction & Reasoning Corpus) agents. The platform itself is an agent: it generates diverse synthetic games targeting the competing agent's weaknesses, and the competing agent trains by solving them.

## Project

- **Stack:** Python 3.14+, numpy, FastAPI (dashboard)
- **Purpose:** Improve an ARC-solving agent via adversarial generation: the trainer creates harder tasks targeting the agent's weaknesses; the agent improves by solving them.
- **Entry point:** `arc3_trainer/cli.py` — invoked as `python -m arc3_trainer.cli`

## Commands

```sh
# Train (adversarial loop)
python3 -m arc3_trainer.cli train --rounds 100 --output-dir ./output

# Evaluate solver on a task or directory
python3 -m arc3_trainer.cli eval --task task.json
python3 -m arc3_trainer.cli eval --dir ./tasks/

# Launch web dashboard
python3 -m arc3_trainer.cli dashboard --host 127.0.0.1 --port 8080

# Export trained solver
python3 -m arc3_trainer.cli export --output solver.py

# Run tests
python3 -m pytest arc3_trainer/tests/
```

## Architecture

The code lives under `arc3_trainer/` with these modules:

| Module | Role |
|---|---|
| `cognitive/` | Core data model: `Grid` (immutable 0-9 int matrix), `ActionDSL` (atomic + composite transformations), `DiffPerception`, `Predictor`, task I/O |
| `agent/` | The competing ARC agent: `Perceiver` (extracts constraints), `Hypothesizer` (candidate actions), `Searcher` (beam search over programs, MDL cost), `Solver` (pipeline entry) |
| `generator/` | Synthetic task generation: `GridGen`, `ProgramSampler`, `TaskPacker`, `DifficultyControl` |
| `trainer/` | Adversarial training loop: `TrainingLoop`, `CurriculumScheduler` (4 stages), `CapabilityProfile` (success-rate matrix), `WeaknessAnalyzer`, `AdversarialSampler` |
| `eval/` | Standard ARC task evaluation: `Evaluator`, `TaskScore` |
| `dashboard/` | FastAPI web app with SSE events (`events.py`, `server.py`, `static/`) |

**Data flow:** `Generator → Task → Agent(Solver) → Result → CapabilityProfile → WeaknessAnalyzer → AdversarialSampler → Generator`

## Conventions

- **Imports:** `from __future__ import annotations` at top of every module.
- **Types:** type annotations on all functions and dataclasses, use `Optional`, `List`, `Dict` from `typing`. numpy arrays typed as `np.ndarray`.
- **Immutability:** `Grid` is immutable (methods return new instances); internal storage is `np.int8`.
- **Logging:** `logging.getLogger(__name__)` — log instead of print.
- **Testing:** `unittest.TestCase` in `tests/`. Use `setUp` for fixtures. Test names use `test_<unit>_<scenario>`.
- **Error handling:** high-level IO wraps in try/except with `logger.warning`; core cognitive/agent code uses `raise ValueError`.
- **No framework config** (no pyproject.toml, setup.py, requirements.txt — dependencies managed externally).

## Notes

<!-- Quick-add section for future context. -->
