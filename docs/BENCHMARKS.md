# Measurements to collect before adding numbers to your resume

First run the smoke check and ensure two fresh healthy targets are present.
Benchmark the same endpoint and path each time; testing Gunicorn directly is a
different experiment from going through Nginx or the AWS ALB. The following is a
GET `/api/targets` read benchmark, not a benchmark of worker ingestion throughput.

```bash
python3 scripts/benchmark.py --url http://127.0.0.1:8080/api/targets   --requests 500 --concurrency 10 --output results/local-c10.json
python3 scripts/benchmark.py --url http://127.0.0.1:8080/api/targets   --requests 1000 --concurrency 25 --output results/local-c25.json
```

For EKS, use the ALB/custom hostname URL from a permitted source IP. Run several
trials and keep all results. Do not extrapolate a brief successful burst to
sustainable throughput. Benchmark a representative seeded database rather than
an empty history. Use the same dataset, node types, replica counts, request count,
and client placement for comparisons.

The script reports successful requests per wall-clock second, error percentage,
and nearest-rank p50/p95/p99 latency over successful requests. Five warmup requests
are excluded. A request has a 10-second timeout. Failures do not contribute to
latency percentiles, so always report the error rate alongside latency. The
client uses Python threads and independent HTTP requests; it can itself bottleneck.
This is evidence for the tested scenario, not the server's maximum capacity.

Record the following with every trial:

| Field | Record |
|---|---|
| Test identity | Git commit, image tags/digests, timestamp, command |
| Deployment | Docker or EKS; region; nodes/instance types; API replica count |
| Client | CPU/RAM, OS, location relative to deployment |
| Workload | URL, concurrency, requests, warmup, stored row count |
| Request results | Successful requests/s, p50/p95/p99, errors |
| Resources | CPU/memory observations during the run, with sampling interval |
| Changes | Any HPA scaling, pod restarts, unrelated traffic |

Docker resources can be observed during the benchmark with `docker stats` in a
second terminal. On EKS, after installing metrics-server, sample
`kubectl top pods -n netops --containers` and `kubectl top nodes` in a separate
terminal. These are samples, not automatically measured peaks or averages; retain
samples if reporting an average/maximum. Full time-series monitoring is Project 3.

## Image size comparison

```bash
bash scripts/measure-images.sh
```

This builds the frontend's build stage and runtime stage separately and records
local Docker uncompressed image sizes. The baseline includes Node, build tools,
source, and dependencies; the runtime contains Nginx and compiled assets. Identify
that baseline honestly. It is not a compressed ECR transfer-size comparison or an
API image-size result. The script's percentage is `(1 - runtime/build) * 100`.
No image-size figure has been measured in the creation environment.

## Reliability evidence

In `docs/OPERATIONS.md`, run the controlled pod replacement and frontend outage.
Record start time, time until Pods become ready, number of failed requests, and
when the dashboard shows a fresh unhealthy/healthy observation. Because probes
run every 10s and the UI refreshes every 5s, detection time includes both sampling
intervals and request timeouts. Repeat the experiment before claiming a recovery
or detection-time result.

A screenshot alone does not establish throughput or an availability percentage.
Keep machine-readable outputs, raw logs, configuration and commands. A resume can
be strong without invented measurements.
