# `packages/contracts`

Shared HTTP/SSE contract between `apps/bridge` (server) and
`apps/pwa` (client). Today the source of truth is the prose spec at
[`../../docs/api.md`](../../docs/api.md); this package is the planned
home for a machine-readable schema once we extract it.

## Roadmap

1. Generate an OpenAPI 3.1 document from the Flask blueprints under
   `apps/bridge/pitwall/features/*/bp_*.py` (script lives in `tools/`,
   TBD).
2. Generate TypeScript types into `apps/pwa/src/shared/api/types.gen.ts`
   from that OpenAPI doc via `openapi-typescript`.
3. Generate Python pydantic models into `apps/bridge/pitwall/_contract.py`
   for symmetry.
4. Add a CI check that fails the build if any handler diverges from
   the published schema.

Until step 1 lands, treat `docs/api.md` as authoritative and the
existing hand-written types in `apps/pwa/src/shared/api/*.ts` as the
client-side mirror.
