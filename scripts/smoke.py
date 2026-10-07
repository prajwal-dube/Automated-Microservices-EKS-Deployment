#!/usr/bin/env python3
import argparse
import json
import time
from urllib.request import urlopen
p=argparse.ArgumentParser()
p.add_argument('--url',default='http://127.0.0.1:8080')
p.add_argument('--timeout',type=int,default=90)
args=p.parse_args()
start=time.monotonic()
last='No response'
while time.monotonic()-start < args.timeout:
    try:
        with urlopen(args.url.rstrip('/')+'/api/targets',timeout=5) as response:
            payload=json.load(response)
        by_name={t['target']:t for t in payload['targets']}
        if all(name in by_name and by_name[name]['healthy'] for name in ['api','frontend']):
            from datetime import datetime, timezone
            age=max((datetime.now(timezone.utc)-datetime.fromisoformat(by_name[n]['observed_at'])).total_seconds() for n in ['api','frontend'])
            if age < 30:
                print(json.dumps({'result':'PASS','targets':payload['targets']},indent=2));break
        last='Waiting for healthy, fresh API and frontend observations'
    except Exception as exc:
        last=type(exc).__name__
    time.sleep(2)
else:
    raise SystemExit('FAIL: '+last)
