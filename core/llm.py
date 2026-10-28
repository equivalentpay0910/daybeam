"""One place to call the LLM, with caching.
Same prompt + same settings = answer comes from disk, so reruns are free and repeatable."""
import hashlib
import json
import os

import diskcache
from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY and DAYBEAM_MODEL from .env

_cache = diskcache.Cache("cache/llm")
_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        key = os.getenv("GEMINI_API_KEY")
        if not key or key == "paste-your-key-here":
            raise RuntimeError("No API key. Copy .env.example to .env and paste your key.")
        _client = genai.Client(api_key=key)
    return _client


def ask(prompt: str, schema=None, temperature: float = 0.0, seed: int = 0) -> dict:
    """Send a prompt, get back {"text": ..., "tokens_in": ..., "tokens_out": ..., "cached": bool}.

    schema: optional Pydantic model; if given, the model must reply in that JSON shape.
    seed:   change it to get a different (but still cached) sample for repeated runs.
    """
    model = os.getenv("DAYBEAM_MODEL", "gemini-3.8-flash")
    key = hashlib.sha256(json.dumps(
        [model, prompt, schema.__name__ if schema else None, temperature, seed]).encode()).hexdigest()
    if key in _cache:
        return {**_cache[key], "cached": True}

    config = {"temperature": temperature}
    if schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_schema"] = schema
    resp = _get_client().models.generate_content(model=model, contents=prompt, config=config)
    usage = getattr(resp, "usage_metadata", None)
    out = {
        "text": resp.text,
        "tokens_in": getattr(usage, "prompt_token_count", 0) or 0,
        "tokens_out": getattr(usage, "candidates_token_count", 0) or 0,
    }
    _cache[key] = out
    return {**out, "cached": False}
