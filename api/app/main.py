"""Small WSGI API. Gunicorn serves it in Docker; no cloud credentials required."""
import hmac
import json
import logging
import math
import os
import re
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from urllib.parse import parse_qs
from .db import Database

LOG = logging.getLogger("netops")
logging.basicConfig(level=logging.INFO, format="%(message)s")
MAX_BODY = 4096
TARGET = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")

class Invalid(Exception):
    pass

def validate(payload):
    if not isinstance(payload, dict):
        raise Invalid("Expected a JSON object")
    target = payload.get("target")
    latency = payload.get("latency_ms")
    code = payload.get("status_code")
    if not isinstance(target, str) or not TARGET.fullmatch(target):
        raise Invalid("target must contain 1-64 letters, digits, dots, underscores or hyphens")
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or not math.isfinite(latency) or not 0 <= latency <= 60000:
        raise Invalid("latency_ms must be a finite number between 0 and 60000")
    if code is not None and (isinstance(code, bool) or not isinstance(code, int) or not 100 <= code <= 599):
        raise Invalid("status_code must be an HTTP status code or null")
    return {"id": str(uuid.uuid4()), "target": target, "latency_ms": round(latency, 3),
            "status_code": code, "healthy": code is not None and 200 <= code < 400,
            "observed_at": time.time()}

def serialize(row):
    keys = ("id", "target", "latency_ms", "status_code", "healthy", "observed_at")
    item = dict(zip(keys, row))
    item["healthy"] = bool(item["healthy"])
    item["observed_at"] = datetime.fromtimestamp(item["observed_at"], timezone.utc).isoformat()
    return item

class Application:
    def __init__(self, db=None):
        self.db = db or Database()

    def __call__(self, env, start_response):
        started = time.monotonic()
        path = env.get("PATH_INFO", "/")
        method = env.get("REQUEST_METHOD", "GET")
        request_id = str(uuid.uuid4())
        status, payload = 500, {"error": "Internal error"}
        try:
            status, payload = self.route(method, path, env)
        except Invalid as exc:
            status, payload = 400, {"error": str(exc)}
        except Exception:
            LOG.exception(json.dumps({"event": "request_failed", "request_id": request_id}))
            status, payload = 503, {"error": "Service temporarily unavailable"}
        body = json.dumps(payload, allow_nan=False).encode()
        start_response(f"{status} {HTTPStatus(status).phrase}", [
            ("Content-Type", "application/json"), ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
            ("X-Request-ID", request_id)])
        LOG.info(json.dumps({"event": "request", "request_id": request_id, "path": path,
                             "method": method, "status": status,
                             "duration_ms": round((time.monotonic()-started)*1000, 3)}))
        return [body]

    def route(self, method, path, env):
        if method == "GET" and path == "/healthz":
            return 200, {"status": "alive"}
        if method == "GET" and path == "/readyz":
            self.db.ready()
            return 200, {"status": "ready"}
        if method == "GET" and path == "/api/targets":
            return 200, {"targets": [serialize(row) for row in self.db.latest()]}
        if method == "GET" and path == "/api/history":
            query = parse_qs(env.get("QUERY_STRING", ""))
            target = query.get("target", [""])[0]
            if not TARGET.fullmatch(target):
                raise Invalid("A valid target is required")
            try:
                limit = int(query.get("limit", ["30"])[0])
            except ValueError:
                raise Invalid("limit must be an integer")
            if not 1 <= limit <= 200:
                raise Invalid("limit must be between 1 and 200")
            return 200, {"history": [serialize(row) for row in self.db.history(target, limit)]}
        if method == "POST" and path == "/api/observations":
            token = os.getenv("INGEST_TOKEN", "")
            supplied = env.get("HTTP_AUTHORIZATION", "")
            if not token or not hmac.compare_digest(supplied.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
                return 401, {"error": "Unauthorized"}
            try:
                length = int(env.get("CONTENT_LENGTH") or "0")
            except ValueError:
                raise Invalid("Invalid content length")
            if length > MAX_BODY:
                return 413, {"error": "Request body exceeds 4096 bytes"}
            if length <= 0:
                raise Invalid("JSON body is required")
            if env.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                return 415, {"error": "Content-Type must be application/json"}
            body = env["wsgi.input"].read(length)
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                raise Invalid("Invalid JSON")
            item = validate(payload)
            self.db.insert(item)
            return 201, item
        if path in ("/healthz", "/readyz", "/api/targets", "/api/history", "/api/observations"):
            return 405, {"error": "Method not allowed"}
        return 404, {"error": "Not found"}

application = Application()
