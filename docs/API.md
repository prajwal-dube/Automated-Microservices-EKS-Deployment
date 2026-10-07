# API contract

| Method | Path | Purpose | Authentication |
|---|---|---|---|
| GET | /healthz | Process responds; no DB dependency | None |
| GET | /readyz | DB connection and observations table available | None |
| GET | /api/targets | Most recent observation per target, sorted by name | None |
| GET | /api/history?target=api&limit=30 | Target history, newest first; limit 1-200 | None |
| POST | /api/observations | Validate and store a probe observation | Bearer INGEST_TOKEN |

POST accepts JSON such as:

```json
{"target":"api","latency_ms":12.345,"status_code":200}
```

Target names must contain 1-64 letters, digits, dots, underscores or hyphens,
starting with a letter or digit. Latency must be a finite number from 0 to 60,000
milliseconds; HTTP status is an integer 100-599 or null for a connection/timeout
failure. Status 200-399 is healthy. Caller-supplied health/timestamps are ignored:
the API computes health and assigns receipt time/ID itself. The receipt timestamp
can differ from probe-start time by probe duration and submission time.

POST returns 201 with the stored observation (receipt timestamp is epoch seconds).
Read endpoints return `targets`/`history` arrays and use UTC ISO timestamps.
POST bodies are capped at 4096 bytes. Invalid data yields 400, invalid ingestion
auth 401, oversized requests 413, wrong content type 415. Database/runtime failures
yield a generic 503 while details go to server logs. Unknown routes yield 404;
unsupported methods on known routes yield 405. JSON responses have no-store,
content-type and request-ID headers. There are no delete/admin/remote-target URLs
available through this API.

Reads are public within the configured network boundary; do not open the lab ALB
to the entire internet without adding reader authentication. The ingest token is
only for service-to-service writes. Keep the token out of frontend code. There is
no user-management or full OAuth system in this learning application.
