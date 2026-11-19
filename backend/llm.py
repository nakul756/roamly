"""One place for language-model calls. Uses any OpenAI-compatible server if LLM_BASE_URL is set (free hosted
tiers such as Groq or OpenRouter with LLM_API_KEY, or a local Ollama), xAI Grok if XAI_API_KEY is set, or the
Anthropic API if ANTHROPIC_API_KEY is set. Returns None when unavailable, so callers always fall back to the rule-based path."""
import json
import os
import urllib.request

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"
XAI_BASE = "https://api.x.ai/v1"
DEFAULT_XAI_MODEL = "grok-4"


def _openai_compat():
    """(base url, api key, model) of the OpenAI-compatible server to use, or None. An explicit LLM_BASE_URL wins over xAI."""
    if os.getenv("LLM_BASE_URL"):
        return os.environ["LLM_BASE_URL"], os.getenv("LLM_API_KEY"), os.getenv("LLM_MODEL", "qwen2.5:3b")
    if os.getenv("XAI_API_KEY"):
        return XAI_BASE, os.environ["XAI_API_KEY"], os.getenv("XAI_MODEL", DEFAULT_XAI_MODEL)
    return None


def mode_name():
    return ("LLM (xAI Grok)" if not os.getenv("LLM_BASE_URL") and os.getenv("XAI_API_KEY") else
            "LLM (OpenAI-compatible server)" if os.getenv("LLM_BASE_URL") else
            "LLM (Anthropic API)" if os.getenv("ANTHROPIC_API_KEY") else "rule-based (no language model configured)")


def llm(system, messages, max_tokens=500, json_mode=False, temperature=0.7, timeout=90):
    compat = _openai_compat()
    key = None if compat else os.getenv("ANTHROPIC_API_KEY")   # a configured free/local/xAI server wins over a paid Anthropic key
    try:
        if key:
            url, headers = "https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}
            body = {"model": os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL), "system": system,
                    "max_tokens": max_tokens, "temperature": temperature, "messages": messages}
        elif compat:
            base, api_key, model = compat
            url = base.rstrip("/") + "/chat/completions"
            headers = {"authorization": "Bearer " + api_key} if api_key else {}
            body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
                    "messages": [{"role": "system", "content": system}] + messages}
            if json_mode:
                body["response_format"] = {"type": "json_object"}   # makes small local models return clean JSON
        else:
            return None
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.load(r)
        return (j["content"][0]["text"] if key else j["choices"][0]["message"]["content"]).strip()
    except Exception:
        return None
