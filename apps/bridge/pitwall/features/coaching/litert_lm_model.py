"""
LitertLmModel — ADK BaseLlm adapter for the Native Android LLM Microservice.

Per ADR-022, the Termux Python environment cannot access the Pixel 10's TPU.
This module acts as a lightweight HTTP client to the native Kotlin app
running on `localhost:8080`. The Kotlin app owns the `LlmInference` engine
and the KV cache.

Environment
-----------
    PITWALL_LITERT_SIDECAR_URL    URL of the Kotlin sidecar (default: http://127.0.0.1:8080)
                                  (legacy: PITWALL_LITERTLM_URL — deprecated)
    PITWALL_LITERT_SIDECAR_MODEL  Model name to request (default: gemma-4-e2b)
                                  (legacy: PITWALL_LITERTLM_MODEL — deprecated)
"""
import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Optional

import aiohttp

from pitwall._env import get_env_with_legacy

_log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_SIDECAR_URL = get_env_with_legacy(
    "PITWALL_LITERT_SIDECAR_URL", "PITWALL_LITERTLM_URL",
    "http://127.0.0.1:8080")
_MODEL_NAME  = get_env_with_legacy(
    "PITWALL_LITERT_SIDECAR_MODEL", "PITWALL_LITERTLM_MODEL",
    "gemma-4-e2b")
_TIMEOUT_S   = 60.0

# ── Tool injection + parsing (Preserved from old implementation) ──────────────

_TOOL_CALL_RE = re.compile(
    r"<function_call>\s*(\{.*?\})\s*</function_call>", re.DOTALL)
_TOOL_CODE_RE = re.compile(
    r"```(?:tool_code|python)\s*\n(.*?)\n```", re.DOTALL)

def _format_tools_for_prompt(tools_dict: dict | None) -> str:
    if not tools_dict:
        return ""
    lines = ["",
             "You have access to these tools. To use one, output ONLY:",
             "<function_call>{\"name\": \"<tool>\", \"args\": {<args>}}</function_call>",
             "Otherwise reply with normal text. Tools available:"]
    for name, decl in (tools_dict or {}).items():
        desc = (getattr(decl, "description", "") or "").strip().splitlines()
        lines.append(f"- {name}: {desc[0] if desc else ''}")
    return "\n".join(lines) + "\n"

def _parse_tool_calls(text: str) -> list[dict]:
    calls: list[dict] = []
    for m in _TOOL_CALL_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name") or obj.get("tool")
        args = obj.get("args") or obj.get("arguments") or {}
        if isinstance(name, str) and isinstance(args, dict):
            calls.append({"name": name, "args": args})
    if calls:
        return calls
    for m in _TOOL_CODE_RE.finditer(text):
        body = m.group(1).strip()
        match = re.match(r"(\w+)\s*\((.*)\)\s*$", body, re.DOTALL)
        if not match:
            continue
        name, args_src = match.group(1), match.group(2)
        try:
            args = _parse_kwargs(args_src)
        except Exception:
            continue
        calls.append({"name": name, "args": args})
    return calls

def _parse_kwargs(src: str) -> dict:
    if not src.strip():
        return {}
    out: dict = {}
    depth = 0
    in_str: str | None = None
    chunks: list[str] = []
    current: list[str] = []
    for ch in src:
        if in_str:
            current.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in "\"'":
            in_str = ch
            current.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            chunks.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        chunks.append("".join(current))
    for chunk in chunks:
        if "=" not in chunk:
            continue
        k, _, v = chunk.partition("=")
        k = k.strip()
        v = v.strip()
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v.strip("'\"")
    return out

def _format_function_response(part) -> str:
    fr = getattr(part, "function_response", None)
    if fr is None:
        return ""
    name = getattr(fr, "name", "tool")
    response = getattr(fr, "response", None) or {}
    try:
        body = json.dumps(response)[:2000]
    except (TypeError, ValueError):
        body = str(response)[:2000]
    return f"<tool_result name=\"{name}\">{body}</tool_result>"

# ── BaseLlm subclass ──────────────────────────────────────────────────────────

HAS_LITERTLM_MODEL = False
try:
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.genai.types import Content, FunctionCall, Part
    HAS_LITERTLM_MODEL = True
except ImportError:
    HAS_LITERTLM_MODEL = False

if HAS_LITERTLM_MODEL:
    class LitertLmModel(BaseLlm):
        model: str = _MODEL_NAME

        async def generate_content_async(
            self, llm_request, stream: bool = False
        ) -> AsyncGenerator[Any, None]:
            
            system_prompt = _extract_system_instruction(llm_request)
            tools_dict = _extract_tools_dict(llm_request)
            history = list(getattr(llm_request, "contents", None) or [])

            if not history:
                yield LlmResponse(
                    error_code="EMPTY_REQUEST",
                    error_message="No contents in llm_request",
                    partial=False, turn_complete=True,
                )
                return

            last = history[-1]
            last_text = _content_text(last)
            if not last_text:
                yield LlmResponse(
                    error_code="EMPTY_USER_MESSAGE",
                    error_message="Last content has no text",
                    partial=False, turn_complete=True,
                )
                return

            full_system = system_prompt + _format_tools_for_prompt(tools_dict)
            
            # The Kotlin server uses the session_id to manage the KV cache.
            # ADK provides a turn-level session_id in the llm_request config if set,
            # otherwise we fallback to a default.
            session_id = "default_adk_session"
            if hasattr(llm_request, "config") and hasattr(llm_request.config, "session_id"):
                 session_id = llm_request.config.session_id or session_id

            messages = []
            if full_system:
                messages.append({"role": "system", "content": full_system})
            
            for c in history[:-1]:
                t = _content_text(c)
                if t:
                    messages.append({"role": _content_role(c), "content": t})
            
            messages.append({"role": "user", "content": last_text})

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": bool(stream),
                "session_id": session_id
            }

            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{_SIDECAR_URL}/v1/chat/completions"
                    async with session.post(url, json=payload, timeout=_TIMEOUT_S) as resp:
                        if resp.status != 200:
                            err_txt = await resp.text()
                            raise RuntimeError(f"Sidecar HTTP {resp.status}: {err_txt}")

                        if stream:
                            accum_text = ""
                            async for line in resp.content:
                                line_str = line.decode('utf-8').strip()
                                if not line_str or line_str.startswith(':') or line_str == "data: [DONE]":
                                    continue
                                if line_str.startswith("data: "):
                                    try:
                                        chunk = json.loads(line_str[6:])
                                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if delta:
                                            accum_text += delta
                                            yield LlmResponse(
                                                content=Content(role="model", parts=[Part(text=delta)]),
                                                partial=True, turn_complete=False,
                                            )
                                    except json.JSONDecodeError:
                                        continue
                            
                            # Finalize for tool calls
                            async for r in self._finalize(accum_text):
                                yield r
                        else:
                            data = await resp.json()
                            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            async for r in self._finalize(text):
                                yield r

            except Exception as exc:
                _log.exception("LitertLmModel call to Kotlin sidecar failed")
                yield LlmResponse(
                    error_code="SIDECAR_ERROR",
                    error_message=f"{type(exc).__name__}: {exc}",
                    partial=False, turn_complete=True,
                )

        async def _finalize(self, text: str) -> AsyncGenerator[Any, None]:
            calls = _parse_tool_calls(text)
            if calls:
                parts = [
                    Part(function_call=FunctionCall(name=c["name"], args=c["args"]))
                    for c in calls
                ]
                yield LlmResponse(
                    content=Content(role="model", parts=parts),
                    partial=False, turn_complete=True,
                )
                return

            yield LlmResponse(
                content=Content(role="model", parts=[Part(text=text)]),
                partial=False, turn_complete=True,
            )

else:
    class LitertLmModel:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError(
                "LitertLmModel requires google-adk — pip install google-adk")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_system_instruction(llm_request) -> str:
    cfg = getattr(llm_request, "config", None)
    if cfg is None:
        return ""
    si = getattr(cfg, "system_instruction", None)
    if si is None:
        return ""
    if isinstance(si, str):
        return si
    parts = getattr(si, "parts", None)
    if parts:
        return "\n".join(p.text for p in parts if getattr(p, "text", None))
    return str(si)

def _extract_tools_dict(llm_request) -> dict:
    td = getattr(llm_request, "tools_dict", None)
    if isinstance(td, dict) and td:
        return td
    cfg = getattr(llm_request, "config", None)
    if cfg is not None:
        tools_attr = getattr(cfg, "tools", None) or []
        out = {}
        for tool in tools_attr:
            decls = getattr(tool, "function_declarations", None) or []
            for decl in decls:
                name = getattr(decl, "name", None)
                if name:
                    out[name] = decl
        if out:
            return out
    return {}

def _content_text(content) -> str:
    parts = getattr(content, "parts", None) or []
    out: list[str] = []
    for p in parts:
        t = getattr(p, "text", None)
        if t:
            out.append(t)
            continue
        fr = getattr(p, "function_response", None)
        if fr is not None:
            out.append(_format_function_response(p))
    return "\n".join(out).strip()

def _content_role(content) -> str:
    role = getattr(content, "role", None) or "user"
    return "user" if role.lower() == "user" else "assistant"

# The following functions are retained purely as empty stubs so that
# 'bp_diagnostics.py' or 'adk_agents.py' which might import them don't crash.
# The Kotlin sidecar now owns these stats.
def get_queue_stats() -> dict:
    return {"status": "delegated_to_kotlin_sidecar"}

def get_kv_cache_stats() -> dict:
    return {"status": "delegated_to_kotlin_sidecar"}

def reset_all_conversations() -> None:
    pass

