"""Pydantic request/response schemas. Anything that crosses the wire
also has a JSON schema mirror in packages/core-telemetry/schemas/ so
the paddock-dashboard (TS) and edge-daemon (Python) can agree on the
shape without importing from here.
"""
