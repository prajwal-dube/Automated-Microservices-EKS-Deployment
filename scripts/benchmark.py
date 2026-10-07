#!/usr/bin/env python3
"""HTTP read benchmark. Measures this client+network+deployment, not a capacity guarantee."""
import argparse
import concurrent.futures
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
p=argparse.ArgumentParser()
p.add_argument('--url',default='http://127.0.0.1:8080/api/targets')
p.add_argument('--requests',type=int,default=500)
p.add_argument('--concurrency',type=int,default=10)
p.add_argument('--output',default='results/benchmark.json')
args=p.parse_args()
if not 1 <= args.concurrency <= 100 or not 1 <= args.requests <= 100000:
    p.error('Use concurrency 1-100 and requests 1-100000')
def request(_):
    start=time.monotonic()
    try:
        with urlopen(args.url,timeout=10) as response:
            ok=response.status==200 and isinstance(json.load(response).get('targets'),list)
    except Exception:
        ok=False
    return ok,(time.monotonic()-start)*1000
# Warm up; excluded from measured samples.
for i in range(5): request(i)
started=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
    samples=list(pool.map(request,range(args.requests)))
duration=time.monotonic()-started
latencies=sorted(ms for ok,ms in samples if ok)
def percentile(p):
    return round(latencies[max(0,math.ceil(p*len(latencies))-1)],3) if latencies else None
successes=len(latencies)
result={'recorded_at':datetime.now(timezone.utc).isoformat(),'url':args.url,
        'client':{'platform':platform.platform(),'python':platform.python_version()},
        'requests':args.requests,'concurrency':args.concurrency,'warmup_requests':5,
        'duration_seconds':round(duration,3),'successful_requests':successes,
        'successful_requests_per_second':round(successes/duration,3),
        'error_rate_percent':round((args.requests-successes)/args.requests*100,3),
        'successful_latency_ms':{'p50':percentile(.50),'p95':percentile(.95),'p99':percentile(.99)},
        'notes':'Successful samples only for latency; 10s request timeout; client/network limit throughput. Record deployment hardware and CPU/RAM separately.'}
path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if successes==0:raise SystemExit(1)
