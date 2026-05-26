# JSON Schemas — source of truth

Every shape that crosses a runtime boundary (edge-daemon ↔
cloud-backend ↔ paddock-dashboard) lives here as a JSON Schema. The
Python and TypeScript wrappers under `../python/` and
`../typescript/` derive their types from these files.

## Phase 0 deliverables (the contract freeze)

These eight files must be written and stable before any V2 feature
agent starts work. Each is its own short, named PR.

| File | Owner | PRD anchor |
|------|-------|------------|
| `telemetry_frame.schema.json` | platform | §3 / §4.1 |
| `corner_phase.schema.json` | platform | §4.2 |
| `corner_delta.schema.json` | platform | §4.2 |
| `gold_trace.schema.json` | platform | §4.2 |
| `pedagogical_cue.schema.json` | platform | §4.2 (3–7 word cap) |
| `learning_plan.schema.json` | platform | §5.5 (50 KB cap) |
| `biometric_snapshot.schema.json` | platform | §5.1 |
| `paddock_sync_envelope.schema.json` | platform | §6 / §7 |

## Authoring rules

- `$schema` of `https://json-schema.org/draft/2020-12/schema`.
- `$id` of `https://trustable-ai-superapp/<filename>`.
- `additionalProperties: false` on every object — schemas are
  exhaustive, not permissive.
- All numerics carry `unit` in their description (e.g., "m/s",
  "rad/s", "psi"). The DEL math assumes SI; the schema enforces it.
- Time fields are `integer`, epoch milliseconds, named `*_ms`.

## Codegen (planned)

`tools/sync-types.sh` will regenerate:

- `../python/core_telemetry/schemas.py` — pydantic models.
- `../typescript/src/schemas.ts` — zod schemas.

Until that script ships, both wrappers maintain hand-written mirrors
and a CI check validates equivalence against the same golden
fixtures under `../python/tests/golden/`.
