#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${AWS_REGION:=ap-south-1}"
: "${IMAGE_TAG:?Set IMAGE_TAG to a unique value, e.g. a Git commit SHA}"
[[ "$IMAGE_TAG" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]] || { echo "Invalid IMAGE_TAG" >&2; exit 1; }
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
for service in api frontend worker; do
  repo="netops-${service}"
  if ! aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$repo" >/dev/null 2>&1; then
    aws ecr create-repository --region "$AWS_REGION" --repository-name "$repo"       --image-tag-mutability IMMUTABLE --image-scanning-configuration scanOnPush=true >/dev/null
  fi
  docker build --platform linux/amd64 -t "$REGISTRY/$repo:$IMAGE_TAG" "$service"
  docker push "$REGISTRY/$repo:$IMAGE_TAG"
done
printf 'Images pushed with tag %s\n' "$IMAGE_TAG"
