"""Minimal keep-alive HTTPS client (stdlib only).

A small shared pool of open connections per host: a translation request reuses a warm TLS connection instead of
paying a new handshake (measured ≈ 480 ms to opencode.ai). warm() opens one ahead of time — the pipeline calls it at
the first keystroke that will need the service, so the handshake overlaps the typing pause instead of adding to the
reply time. Idle connections older than IDLE_S are discarded (servers close them; a stale socket costs a retry).
Honors the system/user proxy settings (urllib.getproxies, which reads the Windows Internet settings) via CONNECT
tunnels, and the Windows certificate store via the default SSL context.
Errors are classified, never carry request/response bodies (only a short error type/message, see _detail).
"""
from __future__ import annotations

import http.client
import json
import socket
import threading
import time
import urllib.parse
import urllib.request

from .errors import HttpError  # noqa: F401  (re-exported)

IDLE_S = 50.0  # below typical server keep-alive timeouts (Cloudflare ≈ 100 s, many APIs ≈ 60 s)
_ctx = None  # SSL context (Windows certificate store) loaded on the first HTTPS request, not at startup
_lock = threading.Lock()
_idle: dict[tuple, list[tuple[float, http.client.HTTPConnection]]] = {}
_warming: set[tuple] = set()


def _ssl():
    global _ctx
    import ssl
    if _ctx is None:
        _ctx = ssl.create_default_context()
    return ssl, _ctx


def _new(scheme: str, host: str, port: int, timeout: float) -> http.client.HTTPConnection:
    proxies = urllib.request.getproxies()
    proxy = proxies.get(scheme) if not urllib.request.proxy_bypass(host) else None
    if proxy:
        pu = urllib.parse.urlsplit(proxy if "://" in proxy else "http://" + proxy)
        if scheme == "https":
            c = http.client.HTTPSConnection(pu.hostname, pu.port or 80, timeout=timeout, context=_ssl()[1])
        else:
            c = http.client.HTTPConnection(pu.hostname, pu.port or 80, timeout=timeout)
        c.set_tunnel(host, port)
        return c
    if scheme == "https":
        return http.client.HTTPSConnection(host, port, timeout=timeout, context=_ssl()[1])
    return http.client.HTTPConnection(host, port, timeout=timeout)


def _checkout(key: tuple, timeout: float, fresh: bool = False) -> tuple[http.client.HTTPConnection, float]:
    """(connection, idle age in s or -1 if new). Reuses the most recently returned idle connection that isn't too
    old, unless fresh (a hedge must not share the fate of a possibly dead pooled socket)."""
    now = time.monotonic()
    with _lock:
        lst = _idle.get(key, [])
        while lst and not fresh:
            t, c = lst.pop()
            if now - t < IDLE_S and c.sock is not None:
                c.timeout = timeout
                c.sock.settimeout(timeout)
                return c, now - t
            _close(c)
    return _new(*key, timeout), -1.0


def _checkin(key: tuple, c: http.client.HTTPConnection) -> None:
    with _lock:
        lst = _idle.setdefault(key, [])
        lst.append((time.monotonic(), c))
        while len(lst) > 2:
            _close(lst.pop(0)[1])


def _close(c) -> None:
    try:
        c.close()
    except Exception:  # noqa: BLE001
        pass


def _key(url: str) -> tuple:
    u = urllib.parse.urlsplit(url)
    return (u.scheme, u.hostname, u.port or (443 if u.scheme == "https" else 80))


def warm(url: str, timeout: float = 8.0) -> bool:
    """Open a connection to url's host ahead of a request (no request is sent). False if one is already idle or
    being opened, or the connect fails (the real request will then report the error)."""
    key = _key(url)
    if key[0] not in ("http", "https") or not key[1]:
        return False
    with _lock:
        fresh = [c for t, c in _idle.get(key, []) if time.monotonic() - t < IDLE_S - 5]
        if fresh or key in _warming:
            return False
        _warming.add(key)
    try:
        c = _new(*key, timeout)
        c.connect()
        _checkin(key, c)
        return True
    except OSError:
        return False
    finally:
        with _lock:
            _warming.discard(key)


def request(method: str, url: str, headers: dict, body: dict | None, timeout: float, fresh: bool = False) -> dict:
    """JSON in, JSON out. Raises HttpError with a classification."""
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise HttpError("badUrl")
    key = _key(url)
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    hdrs = {"Accept": "application/json", "User-Agent": "Translate/0.5", **headers}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    for attempt in (0, 1):  # one retry when a kept-alive connection was closed by the server
        c, age = _checkout(key, timeout, fresh)
        reused = age >= 0
        conn = f"reused {age:.0f}s" if reused else "new"
        try:
            if c.sock is None:
                try:
                    c.connect()  # a connect that stalls or is refused means unreachable, not a slow service
                except OSError:  # ssl.SSLError is an OSError
                    _close(c)
                    raise HttpError("network") from None
            c.request(method, path, body=data, headers=hdrs)
            r = c.getresponse()
            raw = r.read()
            break
        except (socket.timeout, TimeoutError):
            _close(c)
            e = HttpError("timeout")
            e.conn = conn
            raise e from None
        except (http.client.RemoteDisconnected, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, http.client.CannotSendRequest):
            _close(c)
            if attempt or not reused:
                raise HttpError("network") from None
        except (OSError, http.client.HTTPException):  # incl. ssl.SSLError
            _close(c)
            raise HttpError("network") from None
    if r.getheader("Connection", "").lower() == "close" or r.will_close:
        _close(c)
    else:
        _checkin(key, c)
    detail = _detail(raw) if r.status >= 400 else ""
    if r.status in (401, 403):
        raise HttpError("auth", r.status, detail=detail)
    if r.status == 404:
        raise HttpError("notFound", r.status, detail=detail)
    if r.status == 429:
        try:
            ra = float(r.getheader("Retry-After") or 0)
        except ValueError:
            ra = 0.0
        raise HttpError("rate", r.status, ra, detail)
    if r.status >= 400:
        raise HttpError("http", r.status, detail=detail)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HttpError("parse", r.status) from None


def _detail(raw: bytes) -> str:
    """'<type>: <message>' from a JSON error body (OpenAI/Claude/Gemini/OpenCode shapes), ≤ 200 chars."""
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return ""
    err = obj.get("error", obj) if isinstance(obj, dict) else {}
    if isinstance(err, str):
        return err[:200]
    if not isinstance(err, dict):
        return ""
    kind = str(err.get("type") or err.get("code") or err.get("status") or "")
    msg = str(err.get("message") or "")
    return (f"{kind}: {msg}" if kind and msg else kind or msg)[:200]
