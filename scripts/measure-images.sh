#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Compare the frontend build-stage image with its production runtime stage.
docker build --target build -t netops-frontend:build-stage frontend
docker build --target runtime -t netops-frontend:runtime frontend
BUILD_BYTES=$(docker image inspect netops-frontend:build-stage --format '{{.Size}}')
RUNTIME_BYTES=$(docker image inspect netops-frontend:runtime --format '{{.Size}}')
export BUILD_BYTES RUNTIME_BYTES
python3 - <<'PYCODE'
import json, os
from pathlib import Path
before=int(os.environ['BUILD_BYTES']);after=int(os.environ['RUNTIME_BYTES'])
result={'comparison':'Frontend build stage versus production runtime stage',
        'build_stage_bytes':before,'runtime_bytes':after,
        'size_reduction_percent':round((1-after/before)*100,2),
        'size_type':'Docker local uncompressed image size; not registry transfer size'}
Path('results').mkdir(exist_ok=True)
Path('results/image-sizes.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PYCODE
