"""Translation services: presets, request shapes for the wire formats, response parsing.

Wire formats ("protocol"):
  openai     Chat Completions (OpenAI, Grok/xAI, DeepSeek, most OpenCode Go models, most custom gateways)
  responses  OpenAI Responses API (OpenCode Go's GPT/Grok/Muse models)
  anthropic  Claude Messages API (Claude; OpenCode Go's Claude/MiniMax/Qwen models)
  gemini     Google Gemini generateContent

OpenCode Go (opencode.ai/zen/go/v1) routes each model to one of three endpoints and refuses any request without an
`x-opencode-session` header (400 MissingSessionID, before the key is even checked). Its docs also ask clients to
identify themselves with their own user agent. Both are sent; see _OPENCODE_* below.
Authentication ("auth"): bearer (Authorization: Bearer …; API keys, tokens, plan keys), x-api-key, x-goog-api-key,
header (custom header name), query (custom query parameter), none.

The Claude adapter calls the Messages API over HTTPS directly instead of the anthropic SDK: the backend is stdlib-only
by design (resident memory budget, frozen-build size) and talks to six providers through one HTTP client.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import uuid

from .errors import HttpError


def _http():
    from . import http  # loads http.client + ssl on the first service call only
    return http

PRESETS: dict[str, dict] = {
    "openai": {"protocol": "openai", "endpoint": "https://api.openai.com/v1", "model": "gpt-6-luna", "auth": "bearer"},
    "claude": {"protocol": "anthropic", "endpoint": "https://api.anthropic.com", "model": "claude-opus-5-5", "auth": "x-api-key"},
    "gemini": {"protocol": "gemini", "endpoint": "https://generativelanguage.googleapis.com/v1beta", "model": "gemini-flash-latest", "auth": "x-goog-api-key"},
    "grok": {"protocol": "openai", "endpoint": "https://api.x.ai/v1", "model": "grok-4.20", "auth": "bearer"},
    "opencode-go": {"protocol": "openai", "endpoint": "https://opencode.ai/zen/go/v1", "model": "deepseek-v4-flash", "auth": "bearer"},
    "deepseek": {"protocol": "openai", "endpoint": "https://api.deepseek.com", "model": "deepseek-v4-flash", "auth": "bearer"},
    "custom": {"protocol": "openai", "endpoint": "", "model": "", "auth": "bearer"},
}

LANG = {"en": "English", "ja": "Japanese", "ko": "Korean", "fr": "French", "de": "German", "es": "Spanish", "ru": "Russian"}

SYSTEM = (
    "You translate Chinese input-method candidates into {lang}. Each candidate is a word or phrase the user may "
    "insert into a text field instead of the Chinese. Reply with only a JSON object that maps each id to its "
    "translation: natural and concise, as the user would type it, no explanations, no quotes, no alternatives. "
    "Transliterate names. Keep numbers and punctuation as they are."
)

# OpenCode Go: which endpoint each model family needs (docs: opencode.ai/docs/go#endpoints). Everything else uses
# chat/completions. One stable session id per app run, as their routing and prompt caching expect.
_OPENCODE_MESSAGES = re.compile(r"^(claude-|minimax-|qwen)")
_OPENCODE_RESPONSES = re.compile(r"^(gpt-|grok-|muse-)")
_OPENCODE_SESSION = "translate-" + uuid.uuid4().hex


def new_session() -> None:
    """Start a new OpenCode session id — after a request hung (its upstream route may be stuck)."""
    global _OPENCODE_SESSION
    _OPENCODE_SESSION = "translate-" + uuid.uuid4().hex

# Reasoning off. Translating a candidate is a short, simple task, and models that think first answered in 3–10 s
# (30 s worst) instead of ≈ 2 s on OpenCode Go (measured, docs/stage5-report.md). The switch is vendor-specific, so it
# is chosen by model family; a service that rejects it gets one retry without it, and that model is remembered.
_FAST = [
    ("openai", re.compile(r"^(deepseek|kimi)"), {"thinking": {"type": "disabled"}}),
    ("openai", re.compile(r"^(glm|mimo|gpt-[5-9]|o\d)"), {"reasoning_effort": "none"}),
    ("responses", re.compile(r"^(gpt-|muse-|o\d)"), {"reasoning": {"effort": "none"}}),
    ("anthropic", re.compile(r"^(qwen|minimax)"), {"thinking": {"type": "disabled"}}),
    ("gemini", re.compile(r"^gemini"), {"generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}}}),
]
_NO_FAST: set[tuple[str, str]] = set()  # (endpoint, model) that rejected the switch


def _fast(svc: dict) -> dict:
    if (svc.get("endpoint"), svc.get("model")) in _NO_FAST:
        return {}
    for proto, rx, params in _FAST:
        if svc["protocol"] == proto and rx.match(svc.get("model", "")):
            return params
    return {}


def _merge(body: dict, extra: dict) -> None:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(body.get(k), dict):
            _merge(body[k], v)
        else:
            body[k] = v


# Claude models that take output_config.effort and the server-side refusal fallback (see claude-api reference).
_CLAUDE_EFFORT = re.compile(r"^claude-(opus|sonnet|haiku|fable|mythos)-(5|4-[6-9])")
_CLAUDE_FALLBACK = re.compile(r"^claude-(opus-5-5|opus-5|fable-5-1|sonnet-5-5)$")


def resolve(service: dict) -> dict:
    """Preset defaults overlaid with the user's settings for that provider."""
    pid = service.get("provider", "openai")
    base = dict(PRESETS.get(pid, PRESETS["custom"]))
    for k in ("protocol", "endpoint", "model", "auth", "authName"):
        v = service.get(k)
        if v:
            base[k] = v
    if pid != "custom":
        base["protocol"] = PRESETS[pid]["protocol"]  # presets have a fixed wire format
    if pid == "opencode-go":
        m = base.get("model", "")
        base["protocol"] = "anthropic" if _OPENCODE_MESSAGES.match(m) else "responses" if _OPENCODE_RESPONSES.match(m) else "openai"
    base["provider"] = pid
    return base


def _opencode(svc: dict) -> bool:
    return "opencode.ai" in svc.get("endpoint", "")


def needs_key(svc: dict) -> bool:
    return svc.get("auth") != "none"


def _auth(svc: dict, key: str, headers: dict, url: str) -> str:
    a = svc.get("auth", "bearer")
    if _opencode(svc):
        headers["x-opencode-session"] = _OPENCODE_SESSION
        if svc["protocol"] == "anthropic":
            headers["x-api-key"] = key  # its Anthropic-format endpoint takes the same key as an Anthropic client sends it
    if a == "bearer":
        headers["Authorization"] = "Bearer " + key
        if svc["protocol"] == "anthropic" and not _opencode(svc):
            headers["anthropic-beta"] = ",".join(filter(None, [headers.get("anthropic-beta"), "oauth-2025-04-20"]))
    elif a == "x-api-key":
        headers["x-api-key"] = key
    elif a == "x-goog-api-key":
        headers["x-goog-api-key"] = key
    elif a == "header":
        headers[svc.get("authName") or "Authorization"] = key
    elif a == "query":
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({svc.get("authName") or "key": key})
    return url


def build(svc: dict, key: str, texts: dict[int, str], target: str, fast: bool = True) -> tuple[str, dict, dict]:
    """(url, headers, body) for one batch: {n: candidate} → JSON {"n": translation}."""
    system = SYSTEM.format(lang=LANG.get(target, target))
    user = json.dumps({str(n): t for n, t in texts.items()}, ensure_ascii=False)
    ep = svc["endpoint"].rstrip("/")
    headers: dict = {}
    p = svc["protocol"]
    if p == "anthropic":
        url = ep + ("/messages" if ep.endswith("/v1") else "/v1/messages")
        headers["anthropic-version"] = "2023-06-01"
        body = {"model": svc["model"], "max_tokens": 4096, "system": system, "messages": [{"role": "user", "content": user}]}
        if _CLAUDE_EFFORT.match(svc["model"]):
            body["output_config"] = {"effort": "low"}  # a short, simple task: lowest latency and spend
        if _CLAUDE_FALLBACK.match(svc["model"]) and "api.anthropic.com" in ep:
            body["fallbacks"] = "default"  # a classifier decline is retried server-side instead of failing the row
            headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
    elif p == "responses":
        url = ep + "/responses"
        # The Responses API requires the word "json" in the input itself when json_object output is requested.
        body = {"model": svc["model"], "instructions": system, "input": "Candidates (reply with the JSON object): " + user}
        if svc.get("jsonMode", True):
            body["text"] = {"format": {"type": "json_object"}}
    elif p == "gemini":
        url = f"{ep}/models/{urllib.parse.quote(svc['model'], safe='-._')}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json"}}
    else:
        url = ep + "/chat/completions"
        body = {"model": svc["model"], "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if svc.get("jsonMode", True):
            body["response_format"] = {"type": "json_object"}
    if fast:
        _merge(body, _fast(svc))
    url = _auth(svc, key, headers, url)
    return url, headers, body


def text_of(svc: dict, resp: dict) -> str:
    p = svc["protocol"]
    try:
        if p == "anthropic":
            if resp.get("stop_reason") == "refusal":
                raise HttpError("refused")
            return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        if p == "gemini":
            parts = resp["candidates"][0]["content"]["parts"]
            return "".join(x.get("text", "") for x in parts if not x.get("thought"))
        if p == "responses":
            if resp.get("output_text"):
                return resp["output_text"]
            return "".join(c.get("text", "") for o in resp.get("output", []) if o.get("type") == "message"
                           for c in o.get("content", []) if c.get("type") == "output_text")
        return resp["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise HttpError("parse") from None


def parse_map(text: str) -> dict[int, str]:
    """The model's JSON object → {n: translation}; tolerant of code fences and surrounding prose."""
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        raise HttpError("parse")
    try:
        obj = json.loads(text[i:j + 1])
    except ValueError:
        raise HttpError("parse") from None
    out = {}
    for k, v in obj.items():
        if str(k).isdigit() and isinstance(v, str) and v.strip():
            out[int(k)] = v.strip()
    return out


def translate(svc: dict, key: str, texts: dict[int, str], target: str, timeout: float, hedge: bool = False) -> dict[int, str]:
    url, headers, body = build(svc, key, texts, target)
    if hedge and "x-opencode-session" in headers:
        headers["x-opencode-session"] = "translate-" + uuid.uuid4().hex  # don't follow the stuck route
    try:
        resp = _http().request("POST", url, headers, body, timeout, fresh=hedge)
    except HttpError as e:
        if e.kind != "http" or e.status != 400 or not _fast(svc):
            raise
        _NO_FAST.add((svc.get("endpoint"), svc.get("model")))  # the reasoning switch was refused: plain request
        url, headers, body = build(svc, key, texts, target, fast=False)
        resp = _http().request("POST", url, headers, body, timeout)
    return parse_map(text_of(svc, resp))


def warm(svc: dict) -> bool:
    """Open the HTTPS connection for this service ahead of the first request (see http.warm)."""
    ep = svc.get("endpoint", "")
    return bool(ep) and _http().warm(ep)


def test(svc: dict, key: str, target: str, timeout: float) -> dict:
    """Connection test with a real one-word request. Returns {ok, ms} or {ok: False, error}."""
    if needs_key(svc) and not key:
        return {"ok": False, "error": "noKey"}
    if not re.match(r"^https?://", svc.get("endpoint", "")):
        return {"ok": False, "error": "badUrl"}
    if not svc.get("model"):
        return {"ok": False, "error": "noModel"}
    t0 = time.perf_counter()
    try:
        out = translate(svc, key, {1: "测试"}, target, timeout)
    except HttpError as e:
        # The test request carries only "测试", so the service's own error text is safe to show (helps diagnose
        # endpoint / model / format / key problems). Never shown or logged for real translations.
        return {"ok": False, "error": e.kind, "status": e.status, "detail": e.detail}
    if 1 not in out:
        return {"ok": False, "error": "parse"}
    return {"ok": True, "ms": round((time.perf_counter() - t0) * 1000)}


def models(svc: dict, key: str, timeout: float) -> list[str]:
    """Model ids the service lists (OpenAI-compatible /models, Claude /v1/models, Gemini /models)."""
    ep = svc["endpoint"].rstrip("/")
    headers: dict = {}
    p = svc["protocol"]
    if p == "anthropic":
        url = ep + ("/models" if ep.endswith("/v1") else "/v1/models") + "?limit=100"
        headers["anthropic-version"] = "2023-06-01"
    else:
        url = ep + "/models" + ("?pageSize=200" if p == "gemini" else "")
    url = _auth(svc, key, headers, url)
    resp = _http().request("GET", url, headers, None, timeout)
    if p == "gemini":
        ids = [m.get("name", "").removeprefix("models/") for m in resp.get("models", [])
               if "generateContent" in m.get("supportedGenerationMethods", [])]
    else:
        ids = [m.get("id", "") for m in resp.get("data", [])]
    return sorted({i for i in ids if i})
