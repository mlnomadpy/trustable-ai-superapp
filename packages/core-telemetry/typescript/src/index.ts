// @trustable/core-telemetry — TypeScript wrapper.
//
// Mirrors the Python package at packages/core-telemetry/python/.
// Both wrap the JSON Schemas under packages/core-telemetry/schemas/
// — schemas are the source of truth.
//
// Public exports land here as the Phase 0 contract freeze closes:
//   - schemas/*       zod mirrors of schemas/*.schema.json
//   - corner_phase    Entry/Apex/Exit classifier (DEL §4.2)
//   - delta           gold-trace differential math (DEL §4.2)
//   - duckdb_views    curated views over .vbo + CAN for paddock mode
//   - tracks          track metadata loader
//   - learning_plan   cold→hot path JSON validator (<50 KB cap)

export const CORE_TELEMETRY_VERSION = "0.1.0" as const;
