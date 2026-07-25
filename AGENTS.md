# ARC3 Runner Agent Notes

## Project Shape

ARC3 Runner is a local ARC-AGI-3 agent runner and trajectory audit UI.

Core files:

- `server/main.py`: FastAPI API, official ARC runtime, run snapshots, simple agent policy.
- `web/src/App.tsx`: top-level React state and layout.
- `web/src/components/`: UI components for frames, timelines, details, inspectors.
- `web/src/types.ts`: frontend data contract.
- `web/src/demo.ts`: offline demo fixture.
- `docs/doc.md`: current product notes and desired interaction changes.
- `plans/`: executable plans and handoff notes for larger work.

## Standard Workflow

For non-trivial changes:

1. Read `README.md`, `docs/doc.md`, the latest relevant file in `plans/`, and the files you will touch.
2. Preserve the existing ARC run data contract unless the plan explicitly requires a backend schema change.
3. Keep edits narrow and source-aware. Prefer extending existing React/CSS patterns over introducing a new framework.
4. Update or create a plan in `plans/` when turning rough product notes into implementation work.
5. Put handoff-ready context in the plan: goal, source evidence, file map, task order, acceptance checks, and verification commands.
6. Before handing work to another model, state exactly what is done, what remains, which files changed, and which commands passed or failed.

## Current Product Direction

The interface should converge on these rules:

- Environments live in the top bar as compact status squares.
- The rendered frame, action space, observations, candidate actions, selected action, and environment response form one "visual game interface".
- Every frame has two equivalent representations: visual interface and data interface.
- Past frames are visible as a draggable sequence, with gallery, list, and timeline views.
- Replay means playing existing recorded steps.
- Rerun/replay-as-agent means creating a new run with the selected strategy.
- JSON, arrays, and frame matrices must be compact and scannable; avoid default pretty printing that puts every number on its own line.

## Verification Commands

Use these before claiming implementation is complete:

```bash
make test
make lint
make build
```

For local manual checks:

```bash
make dev
```

Default endpoints:

- Web: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8010`
- API docs: `http://127.0.0.1:8010/docs`

## Handoff Format

When handing to another model, include:

- Objective.
- Relevant plan path.
- Files already changed.
- Files likely next.
- Commands run and results.
- Known blockers or assumptions.
- The smallest next action.

Do not duplicate long plan content in chat when a plan file already exists. Link or reference the plan path instead.
