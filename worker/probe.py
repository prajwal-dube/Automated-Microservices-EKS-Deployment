"""Periodic real HTTP probes. Destinations are configured by the operator only."""
import json
import logging
import os
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger("probe")
RUNNING = True

def stop(*_):
    global RUNNING
    RUNNING = False

def measure(target, timeout=3):
    start = time.monotonic()
    status = None
    try:
        with urlopen(target["url"], timeout=timeout) as response:
            status = response.status
            response.read(1024)
    except HTTPError as exc:
        status = exc.code
        exc.close()
    except (URLError, TimeoutError, OSError):
        pass
    return {"target": target["name"], "latency_ms": round((time.monotonic() - start)*1000, 3), "status_code": status}

def submit(api_url, token, observation):
    request = Request(api_url.rstrip("/") + "/api/observations",
                      data=json.dumps(observation).encode(), method="POST",
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urlopen(request, timeout=5) as response:
        if response.status != 201:
            raise RuntimeError("Ingestion failed")
        response.read()

def config():
    targets = json.loads(os.environ["PROBE_TARGETS"])
    if not isinstance(targets, list) or not targets or len(targets) > 20:
        raise ValueError("Configure between 1 and 20 targets")
    import re
    seen = set()
    for target in targets:
        if not isinstance(target, dict) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", target.get("name", "")):
            raise ValueError("Invalid target name")
        parsed = urlparse(target["url"])
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use HTTP(S) URLs without credentials")
        if target["name"] in seen:
            raise ValueError("Target names must be unique")
        seen.add(target["name"])
    interval = int(os.getenv("PROBE_INTERVAL_SECONDS", "10"))
    if interval < 1:
        raise ValueError("Interval must be at least one second")
    if not os.environ.get("INGEST_TOKEN"):
        raise ValueError("INGEST_TOKEN is required")
    return targets, interval

def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    targets, interval = config()
    while RUNNING:
        started = time.monotonic()
        for target in targets:
            if not RUNNING:
                break
            observation = measure(target)
            try:
                submit(os.getenv("API_URL", "http://api:8000"), os.environ["INGEST_TOKEN"], observation)
                LOG.info(json.dumps({"event": "probe", **observation}))
            except Exception:
                # Never log bearer tokens, URLs containing credentials, or response bodies.
                LOG.warning(json.dumps({"event": "submit_failed", "target": target["name"]}))
        remaining = max(0, interval - (time.monotonic() - started))
        while RUNNING and remaining > 0:
            step = min(remaining, 0.5)
            time.sleep(step)
            remaining -= step

if __name__ == "__main__":
    main()
