"""
Validate the LiteRT-LM coaching stack on a real Pixel running Termux.

This is the smoke test that the architecture in ADR-012 + ADR-013 actually
works on the target hardware. Run it on a physical Pixel inside Termux —
it does NOT exercise anything useful on a desktop dev machine.

Steps the script performs:
    1. Confirm `mediapipe` is installed.
    2. Confirm `mediapipe.tasks.python.genai.inference.LlmInference` imports.
    3. Locate the Gemma 4 LiteRT-LM .task file.
    4. Construct an LlmInferenceOptions + create the engine.
    5. Run a tiny inference with a fixed prompt; record wall-clock latency.
    6. Print PASS / FAIL with a one-line reason.

Usage on a Pixel inside Termux:
    pkg install python git
    pip install mediapipe
    mkdir -p ~/storage/shared/Pitwall/models/
    # Push gemma-4-E2B-it.task to that dir (adb push from a desktop, or
    # wget from huggingface.co/litert-community/gemma-4-E2B-it-litert-lm)
    git clone <this-repo>
    python3 pitwall/tools/validate_litert.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

DEFAULT_MODEL_PATHS = [
    "~/storage/shared/Pitwall/models/gemma-4-E2B-it.task",
    "models/gemma-4-E2B-it.task",
    "/sdcard/Pitwall/models/gemma-4-E2B-it.task",
]

DEFAULT_PROMPT = (
    "You are a rally co-driver at Sonoma Raceway. Reply in ONE short line, "
    "no more than 10 words. The driver is approaching Turn 11, the "
    "hairpin known as Calamity Corner, with the bump on the left as the "
    "brake reference. Speak the pace note now."
)


def banner(title: str):
    """Print a prominent step banner."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def check(condition: bool, ok: str, fail: str) -> bool:
    """Print a ✓/✗ result line and return the condition."""
    print(f"  {'✓' if condition else '✗'}  {ok if condition else fail}")
    return condition


def main():
    """CLI entry point — validate LiteRT-LM on a physical Pixel in Termux."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="",
                    help="Path to Gemma 4 .task; defaults to standard locations")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--max-tokens", type=int, default=24)
    args = ap.parse_args()

    print(f"validate_litert.py — Pitwall LiteRT-LM smoke test")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    print(f"In Termux: {'/data/data/com.termux' in os.environ.get('HOME', '')}")

    # ---- Step 1: mediapipe import -------------------------------------------
    banner("STEP 1 — mediapipe import")
    try:
        import mediapipe  # noqa: F401
        version = getattr(mediapipe, "__version__", "(unknown)")
        check(True, f"mediapipe imported (version {version})", "")
    except ImportError as e:
        check(False, "", f"mediapipe NOT installed: {e}")
        print("\nFAIL — install with:  pip install mediapipe\n")
        return 1

    # ---- Step 2: Genai LlmInference import ----------------------------------
    banner("STEP 2 — mediapipe.tasks.python.genai")
    try:
        from mediapipe.tasks.python.genai import inference  # type: ignore
        check(True,
              "mediapipe.tasks.python.genai.inference imported",
              "")
    except Exception as e:
        check(False, "",
              f"genai inference module did NOT import: {type(e).__name__}: {e}")
        print("\nFAIL — your mediapipe build does not include the Genai task. "
              "Try `pip install --upgrade mediapipe`.\n")
        return 1

    # ---- Step 3: locate model file -----------------------------------------
    banner("STEP 3 — locate Gemma 4 .task file")
    candidates = [args.model] if args.model else DEFAULT_MODEL_PATHS
    found = None
    for c in candidates:
        if not c:
            continue
        p = Path(os.path.expanduser(c))
        if p.exists():
            found = p
            break
    if not found:
        for c in candidates:
            print(f"    × {c}")
        print(f"\nFAIL — no .task file found. Download from:")
        print(f"  huggingface.co/litert-community/gemma-4-E2B-it-litert-lm")
        return 1
    size_mb = found.stat().st_size / (1024 * 1024)
    check(True, f"found {found}  ({size_mb:.1f} MB)", "")

    # ---- Step 4: construct LlmInference -------------------------------------
    banner("STEP 4 — construct LlmInference engine")
    try:
        opts = inference.LlmInferenceOptions(
            model_path=str(found),
            max_tokens=args.max_tokens,
            temperature=0.4,
            top_k=40,
        )
        t0 = time.time()
        llm = inference.LlmInference.create_from_options(opts)
        load_s = time.time() - t0
        check(True, f"engine constructed in {load_s:.2f}s", "")
    except Exception as e:
        check(False, "", f"create_from_options FAILED: {type(e).__name__}: {e}")
        print("\nFAIL — model file may be corrupt, mismatched format, or "
              "unsupported by this mediapipe version.\n")
        return 1

    # ---- Step 5: inference --------------------------------------------------
    banner("STEP 5 — run a single inference")
    try:
        t0 = time.time()
        response = llm.generate_response(args.prompt)
        gen_s = time.time() - t0
    except Exception as e:
        check(False, "", f"generate_response FAILED: {type(e).__name__}: {e}")
        return 1

    if not response or not response.strip():
        check(False, "", "model returned an empty string")
        return 1

    check(True, f"response in {gen_s:.2f}s ({len(response)} chars)", "")
    print(f"\n  >>> {response.strip()[:200]}")

    # ---- Summary -----------------------------------------------------------
    banner("PASS")
    print(f"  mediapipe :  installed")
    print(f"  Genai     :  importable")
    print(f"  model     :  {found.name} ({size_mb:.1f} MB)")
    print(f"  load time :  {load_s:.2f}s")
    print(f"  gen time  :  {gen_s:.2f}s")
    print(f"  hot-path budget (50 ms): {'OK' if gen_s * 1000 < 50 else 'OVER — review --max-tokens or model size'}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
