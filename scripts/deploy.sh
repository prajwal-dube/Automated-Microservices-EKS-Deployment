#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${AWS_REGION:=ap-south-1}"
: "${CLUSTER_NAME:=netops-lab}"
: "${IMAGE_TAG:?Use the IMAGE_TAG pushed by build-push.sh}"
: "${TRUSTED_CIDRS:?Set TRUSTED_CIDRS to your public IPv4 /32 or comma-separated trusted CIDRs}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"
kubectl get secret netops-secrets -n netops >/dev/null
# Write only nonsecret deployment values; commas in CIDRs must not become Helm setters.
OVERRIDES=$(mktemp)
trap 'rm -f "$OVERRIDES"' EXIT
export AWS_REGION IMAGE_TAG TRUSTED_CIDRS REGISTRY
python3 - "$OVERRIDES" <<'PYCODE'
import ipaddress, json, os, sys
cidrs=os.environ['TRUSTED_CIDRS']
for cidr in cidrs.split(','):
    network=ipaddress.ip_network(cidr.strip(), strict=False)
    if network.version != 4 or network.prefixlen == 0:
        raise SystemExit('Use trusted IPv4 CIDRs rather than all internet addresses')
if os.getenv('ACM_CERTIFICATE_ARN') and not os.getenv('DASHBOARD_HOST'):
    raise SystemExit('Set DASHBOARD_HOST to the custom certificate-covered domain for HTTPS')
values={'images':{s:{'repository':os.environ['REGISTRY']+'/netops-'+s,'tag':os.environ['IMAGE_TAG']} for s in ['api','frontend','worker']},
        'ingress':{'inboundCidrs':cidrs,'certificateArn':os.getenv('ACM_CERTIFICATE_ARN',''),'host':os.getenv('DASHBOARD_HOST','')}}
with open(sys.argv[1],'w') as stream: json.dump(values,stream)
PYCODE
helm lint deploy/helm/netops -f "$OVERRIDES"
helm upgrade --install lab deploy/helm/netops -n netops -f "$OVERRIDES"   --atomic --wait --wait-for-jobs --timeout 15m
kubectl get pods,svc,ingress,pvc -n netops
