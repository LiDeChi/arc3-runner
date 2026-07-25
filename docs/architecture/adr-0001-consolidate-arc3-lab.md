# ADR-0001: Consolidate the ARC3 lab around arc3-runner

- Status: Accepted
- Date: 2026-07-25
- Decision owners: ARC3 project owner

## Context

ARC3 work had split across several uncoordinated directories:

- `arc3-runner` contained the only healthy Git history and the primary FastAPI/React product.
- `arc3` contained later decision-visibility UI work but referenced a deleted Git worktree.
- `arc3-math` contained a symbolic DSL, local engine, Bayesian agent, adversarial generator, and a second API/UI.
- a detached Codex worktree contained Dreamer-lite, PBT, offline submission, notebooks, and the existing `arc3.wordm.us` Worker.
- additional static prototypes and cognitive-training documents lived in unrelated folders.

The copies had overlapping APIs and interfaces, different data contracts, generated dependencies,
and no authoritative location. Deleting them directly would lose uncommitted research; merging all
runtime code into one Python package would create dependency and product-boundary coupling.

## Decision

Use `arc3-runner` as the single canonical repository and organize it into four explicit layers:

1. `server/`, `web/`, and `tests/` are the supported product.
2. `packages/arc3-math/` is a separately testable symbolic-reasoning package. Its duplicate API,
   remote adapter, and frontend are not part of the canonical runtime.
3. `experiments/world-model/` is a separately testable Dreamer-lite/PBT research experiment.
4. `deploy/arc3-wordm-us/` preserves the Cloudflare Worker name and route independently of local
   product startup.

Research specifications and prototypes live under `docs/research/` and `docs/archive/`.
Pre-consolidation source is retained on dated `archive/*` Git branches and in a verified local
backup manifest before legacy directories are removed.

The product absorbs the orphan UI's missing decision card, collapsible event detail, training
parameters, trend/reliability charts, episode drilldown, replay, and help drawer. The existing
product backend remains authoritative; its training episode schema is extended with replayable
frames and audit fields rather than replaced with the orphan synthetic runtime.

## Alternatives considered

### Keep every directory as an independent project

Rejected because ownership, startup commands, Git status, and shared concepts remain ambiguous.
Broken worktree metadata would continue to make some copies unsafe to evolve.

### Merge every implementation into one runtime package

Rejected because the product runner, symbolic engine, and Dreamer/PBT experiment have different
contracts and maturity. A single dependency graph would make normal product installation and
testing slower and less reliable.

### Preserve only the newest-looking directory

Rejected because modification time did not correlate with complete Git history or runtime quality.
This would lose unique research and deployment assets.

## Consequences

Positive:

- one canonical clone, issue surface, branch history, startup action, and product data contract;
- symbolic and world-model research remain runnable without contaminating the product runtime;
- decision and training behavior are visible and replayable in the supported UI;
- the existing Cloudflare worker identity and domain route remain stable;
- old source can be removed without losing recoverability.

Negative:

- the repository is larger and contains multiple independently testable Python scopes;
- `make test` must run three suites;
- research packages are not yet wired into the production strategy selector;
- archived branches must be retained as historical source rather than treated as active products.

## Performance implications

Normal API and Web startup do not import either research package. Product installation therefore
keeps the previous dependency graph. Training episode rows now include frame matrices and audit
payloads, increasing SQLite usage; this is bounded by local training parameters and is required for
replay. Trend and reliability charts are dependency-free SVG components.

## Migration

1. Create source-only tar archives and a complete Git bundle.
2. Push the four legacy snapshots to dated `archive/*` branches.
3. Fast-forward the canonical clone to the latest valid product history.
4. Port missing UI and extend training episode persistence/API.
5. Copy symbolic, world-model, deployment, and research assets into the layer structure above.
6. Add unified commands, documentation, and Codex “打开体验”.
7. Run all tests, lint, build, API/UI startup, and repeated-open checks.
8. Push the consolidation, then remove only the validated legacy directories.

## Validation

The decision is accepted when:

- `make test`, `make lint`, and `make build` pass;
- `/api/health` identifies `arc3-runner`;
- a training generation can list episodes and return replayable step frames;
- the Web UI opens on the fixed `127.0.0.1:5174` URL;
- invoking “打开体验” twice reuses the same listeners;
- the deployment configuration still names `arc3-platform-agent` and routes `arc3.wordm.us/*`;
- all archive refs and the backup manifest can be independently verified.
