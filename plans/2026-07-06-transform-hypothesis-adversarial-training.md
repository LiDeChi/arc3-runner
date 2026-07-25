# Transform-Hypothesis Adversarial Training

Source plan: <https://github.com/LiDeChi/arc3-runner/blob/claude/project-overview-xj2b52/plans/2026-07-06-transform-hypothesis-adversarial-training.md>

## Goal

Build a trainable, auditable ARC agent whose decision unit is a spatial transform
hypothesis. The full source plan defines transform hypotheses, imagination frames,
surprise/credibility signals, synthetic trap environments, SQLite-backed training,
and a training visualization mode.

## Local Execution Scope

This checkout is starting with the smallest safe milestone:

1. Add `server/transforms.py` as a standalone Transform DSL.
2. Cover primitive apply/serialization/readable/complexity behavior with tests.
3. Avoid changing `server/main.py` runtime behavior until hypothesis shadow mode is
   implemented.

## Milestone Status

- M0 contract-first frontend/backend event fields: not started locally.
- M1 Transform DSL: complete locally (`server/transforms.py`, `tests/test_transforms.py`).
- M2 hypothesis engine + shadow mode: not started.
- M3 transform-aware policy: not started.
- M4 synthetic environment + traps: not started.
- M5 training loop + SQLite: not started.
- M6 official environment evaluation: not started.

## Acceptance Checks

```bash
make test
make lint
make build
```
