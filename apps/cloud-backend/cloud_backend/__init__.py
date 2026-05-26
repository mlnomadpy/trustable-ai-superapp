"""Trustable AI Super App — cloud backend.

Owns strategic-reasoning workloads that are too heavy for the in-car
edge daemon: cold-path curriculum generation (Gemini 1.5 Pro / 3.0),
post-session debrief synthesis, gold-trace ingestion, and the
Pedagogical RAG store (Ross Bentley vector index).

Runs behind FastAPI/uvicorn in production and on a developer laptop
(or trackside paddock laptop) during air-gapped fallback per PRD
§6.4.
"""

__version__ = "0.1.0"
