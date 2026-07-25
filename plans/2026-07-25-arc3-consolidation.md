# ARC3 project consolidation

## Goal

Make `arc3-runner` the only active ARC3 repository while preserving every unique implementation,
research artifact, deployment route, and recoverable history.

## Source evidence

- `arc3-runner`: only healthy Git clone and most complete supported product.
- orphan `arc3`: later decision/training visibility implementation, broken worktree metadata.
- `arc3-math`: symbolic transform DSL, local engine, Bayesian agent, generator, SQLite/SFT tooling.
- World Model worktree: Dreamer-lite, PBT, notebooks, offline submission, Cloudflare Worker.
- static trainer, Workbuddy prototype, and cognitive framework: useful history or documentation,
  not competing products.

## Target map

- `server/`, `web/`, `tests/`: supported ARC3 Runner product.
- `packages/arc3-math/`: independent symbolic reasoning core.
- `experiments/world-model/`: independent Dreamer/PBT experiment.
- `deploy/arc3-wordm-us/`: existing domain deployment source.
- `docs/research/`: specifications and cognitive framework.
- `docs/archive/ui-prototypes/`: retained static prototype.

## Execution order

1. Verify source inventories and test baselines.
2. Create tar archives, Git bundle, and dated remote archive branches.
3. Port decision/training UI and complete the episode replay contract.
4. Move research and deployment assets into isolated scopes.
5. Add ADR, project map, unified commands, and “打开体验”.
6. Update orchestration metadata to one `arc-lab` canonical repository.
7. Run product, math, world-model, lint, build, API and browser verification.
8. Push the canonical branch/main and remove the validated redundant directories.

## Acceptance checks

```bash
make install
make test
make lint
make build
make open
```

Additional checks:

- parse `.codex/environments/environment.toml` with Python `tomllib`;
- call “打开体验” twice and verify one listener on each fixed port;
- request training generations, episode summaries, episode detail, and knowledge timeline;
- verify the four `archive/*` refs and the Git bundle;
- verify the Worker name/route remain unchanged.

## Cleanup guard

No legacy directory is removed until archive refs are remote, tests/build/startup pass, the
consolidation commit is pushed, and each deletion target is re-listed immediately before removal.
