"""One place to call the LLM, with caching, a speed limit, and automatic retries.

- Cache: same prompt + same settings = answer comes from disk, so reruns are free and repeatable.
- Speed limit: the free tier allows only a few requests per minute (DAYBEAM_RPM, default 5),
  so we wait between calls instead of getting "429 RESOURCE_EXHAUSTED".
- Retries: on 429 (too many requests) or 503 (model busy) we wait and try again, up to 8 times.
  Errors are never cached, so a failed call is retried for real next time.
"""
import hashlib
import json
import os
import re
import time

import diskcache
from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY, DAYBEAM_MODEL, DAYBEAM_RPM from .env (or Colab sets them)

_cache = diskcache.Cache("cache/llm")
_client = None
_last_call = 0.0
MAX_TRIES = 8


def _get_client():
    global _client
    if _client is None:
        from google import genai
        key = os.getenv("GEMINI_API_KEY")
        if not key or key == "paste-your-key-here":
            raise RuntimeError("No API key. In Colab: Secrets (key icon) -> GEMINI_API_KEY, then run the key cell.")
        _client = genai.Client(api_key=key)
    return _client


def _wait_for_rate_limit():
    """Space calls out so we stay under DAYBEAM_RPM requests per minute (0 = no limit)."""
    global _last_call
    rpm = float(os.getenv("DAYBEAM_RPM", "5"))
    if rpm > 0:
        gap = 60.0 / rpm
        wait = _last_call + gap - time.time()
        if wait > 0:
            time.sleep(wait)
    _last_call = time.time()


def _retry_delay(err, attempt):
    """How long to wait before retrying: use Google's suggested delay if it gives one."""
    m = re.search(r"retry in ([\d.]+)s", str(err))
    if m:
        return float(m.group(1)) + 1
    return min(60, 5 * 2 ** attempt)  # 5, 10, 20, 40, 60, 60... seconds


def ask(prompt: str, schema=None, temperature: float = 0.0, seed: int = 0) -> dict:
    """Send a prompt, get back {"text", "tokens_in", "tokens_out", "cached"}.

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

    for attempt in range(MAX_TRIES):
        _wait_for_rate_limit()
        try:
            resp = _get_client().models.generate_content(model=model, contents=prompt, config=config)
            break
        except Exception as e:
            text = str(e)
            busy = ("429" in text or "RESOURCE_EXHAUSTED" in text or "503" in text
                    or "UNAVAILABLE" in text or "500" in text)
            if "PerDay" in text or "per day" in text.lower():
                raise RuntimeError("Daily free-tier limit reached. Results so far are cached; "
                                   "run again tomorrow or turn on billing with a spending cap.") from e
            if not busy or attempt == MAX_TRIES - 1:
                raise
            delay = _retry_delay(e, attempt)
            print(f"  [Gemini busy or rate-limited, waiting {delay:.0f}s, try {attempt + 2}/{MAX_TRIES}]", flush=True)
            time.sleep(delay)

    usage = getattr(resp, "usage_metadata", None)
    out = {
        "text": resp.text,
        "tokens_in": getattr(usage, "prompt_token_count", 0) or 0,
        "tokens_out": getattr(usage, "candidates_token_count", 0) or 0,
    }
    _cache[key] = out
    return {**out, "cached": False}
