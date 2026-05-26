"""core-telemetry — shared schemas, VBO/CAN parsers, and DEL math.

This package is the single source of truth for any data shape that
crosses runtime boundaries (edge-daemon ↔ cloud-backend ↔
paddock-dashboard). The TypeScript mirror lives at
`packages/core-telemetry/typescript/`; both wrap the JSON Schemas
under `packages/core-telemetry/schemas/`.

Public modules land here as the Phase 0 contract freeze closes:

- ``schemas``        pydantic mirrors of schemas/*.schema.json
- ``vbo_parser``     20 Hz GPS log parser
- ``can_decoder``    AiM MXP + cantools wrapper (matches edge-daemon)
- ``corner_phase``   Entry/Apex/Exit state machine (DEL §4.2)
- ``delta``          gold-trace differential math (DEL §4.2)
- ``tracks``         track metadata loader
- ``learning_plan``  cold→hot path JSON validator (<50 KB cap)
"""

__version__ = "0.1.0"
