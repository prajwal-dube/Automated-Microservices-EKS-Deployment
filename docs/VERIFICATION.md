# Verification report

17 offline tests passed with no failures. The tests use isolated SQLite databases,
not PostgreSQL. They include real local HTTP requests, worker measurement and
authenticated submission through the API into persisted history.

Passed: authenticated ingestion (including wrong/non-ASCII tokens), stored
latest/history ordering and limits, invalid JSON/types/statuses/latency, injection-like
invalid target strings, body limits, stale-data retention, process liveness during
DB failure, real success/503/refused-connection probes, submission headers/body,
worker destination validation, Python syntax, shell syntax, non-template YAML,
package.json, and React JSX/Vite configuration syntax parsed with Babel.

Not run here: Docker builds/Compose, React dependency installation and production
build/browser rendering, PostgreSQL runtime integration, Helm lint/render/schema
validation, any actual Kubernetes or AWS deployment, HPA/NetworkPolicy behavior,
HTTP load benchmarks, or image-size comparisons. Docker, Helm, kubectl, and
PostgreSQL are absent; registry access is restricted. The included configurations
must be verified on a machine with those tools and AWS access.

`results/offline-checks.txt` records the actual test output;
`results/verification.json` is the machine-readable report. Their test execution
time is not application performance evidence. No invented image-size reduction,
throughput, latency improvement, recovery time or uptime has been added.

Run `bash scripts/check.sh` with Helm installed, then follow README's Docker and
EKS smoke checks. Keep actual deployment evidence before claiming deployed EKS
experience on your resume. Run BENCHMARKS instructions for quantitative claims.
