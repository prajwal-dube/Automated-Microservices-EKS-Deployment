#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v aws >/dev/null
command -v eksctl >/dev/null
CONFIG=${1:-deploy/eks/cluster.yaml}
if [[ ! -f "$CONFIG" ]] || grep -q 'YOUR_PUBLIC_IP' "$CONFIG"; then
  echo "Copy cluster.yaml to cluster.local.yaml and replace YOUR_PUBLIC_IP/32 first." >&2
  exit 1
fi
aws sts get-caller-identity
# This command creates billable AWS resources; run after checking costs.
eksctl create cluster -f "$CONFIG"
