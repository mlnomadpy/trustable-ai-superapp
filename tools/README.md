# `tools/`

Repo-wide developer utilities — code generators, lints, one-off
migration scripts. Anything that isn't part of an app's runtime and
isn't a recurring deploy step (those live under `deploy/`).

## Planned

- `tools/openapi-extract.py` — walk Flask blueprints, emit OpenAPI 3.1
  to `packages/contracts/openapi.yaml`.
- `tools/sync-types.sh` — regenerate `apps/pwa/src/shared/api/types.gen.ts`
  from the OpenAPI doc.
- `tools/lint-no-fake-data.py` — grep for `?? 0` / `?? []` chains in
  the PWA's store layer (enforces the no-fake-fallback rule).
