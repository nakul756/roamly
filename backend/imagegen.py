"""Destination pictures from an image model: Google Gemini (GEMINI_API_KEY, or the same LLM_API_KEY you use for Gemini chat)
or xAI (XAI_API_KEY). Each city is generated once on first request and kept on disk.
With no key, or if every provider fails, this returns None and the frontend keeps its drawn illustration."""
import base64
import json
import os
import re
import threading
import urllib.request

from config import DB_DIR

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
XAI_URL = "https://api.x.ai/v1/images/generations"
CACHE = DB_DIR / "images"
_locks, _guard = {}, threading.Lock()


def slug(name):
    """Same rule as Art.slug in frontend/js/art.js."""
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", name.lower().split(" → ")[0]))


def _gemini_key():
    if os.getenv("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if "generativelanguage" in os.getenv("LLM_BASE_URL", "") and os.getenv("LLM_API_KEY"):
        return os.environ["LLM_API_KEY"]
    return None


def providers():
    """Providers with a key configured, in the order they are tried."""
    return [p for p, ok in (("xai", os.getenv("XAI_API_KEY")), ("gemini", _gemini_key())) if ok]


def _prompt(city, country, trip_type):
    return (f"A beautiful, realistic travel photograph of {city}, {country}, showing its most recognisable scenery "
            f"({trip_type} destination), golden-hour light, wide landscape composition. No text, no watermark, no people in focus.")


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _generate(provider, prompt, timeout):
    if provider == "gemini":
        j = _post(GEMINI_URL.format(model=os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")),
                  {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["IMAGE"]}},
                  {"x-goog-api-key": _gemini_key()}, timeout)
        for part in j["candidates"][0]["content"]["parts"]:
            data = part.get("inlineData") or part.get("inline_data")
            if data: return base64.b64decode(data["data"])
        raise ValueError("no image in response")
    j = _post(XAI_URL, {"model": os.getenv("XAI_IMAGE_MODEL", "grok-2-image"), "prompt": prompt, "n": 1, "response_format": "b64_json"},
              {"authorization": "Bearer " + os.environ["XAI_API_KEY"]}, timeout)
    return base64.b64decode(j["data"][0]["b64_json"])


def get(city, country, trip_type, timeout=90):
    """Path of the cached image for this city, generating it first if needed. None if unavailable."""
    path = CACHE / f"{slug(city)}.jpg"
    if path.exists():
        return path
    with _guard:
        lock = _locks.setdefault(path.name, threading.Lock())
    with lock:                                    # two visitors asking at once must not pay for two images
        if path.exists():
            return path
        for p in providers():
            try:
                img = _generate(p, _prompt(city, country, trip_type), timeout)
                CACHE.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(img)
                tmp.replace(path)
                return path
            except Exception:
                continue                          # quota, no credit, network: try the next provider
        return None
