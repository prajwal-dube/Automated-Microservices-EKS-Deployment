#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v
for script in scripts/*.sh; do bash -n "$script"; done
sh -n frontend/entrypoint.sh
if command -v helm >/dev/null; then
  helm lint deploy/helm/netops --set ingress.inboundCidrs=127.0.0.1/32
  helm lint deploy/helm/netops -f deploy/helm/netops/values-local.yaml
  helm template lab deploy/helm/netops --set ingress.inboundCidrs=127.0.0.1/32 >/dev/null
  helm template lab deploy/helm/netops --set ingress.inboundCidrs=127.0.0.1/32     --set ingress.certificateArn=arn:aws:acm:ap-south-1:111111111111:certificate/example     --set ingress.host=netops.example.com --set hpa.enabled=true --set networkPolicy.enabled=true >/dev/null
else
  echo "Helm not found: chart lint/render checks skipped."
fi
