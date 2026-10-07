#!/usr/bin/env bash
set -euo pipefail
: "${AWS_REGION:=ap-south-1}"
: "${CLUSTER_NAME:=netops-lab}"
# Controller and chart are a matched, documented pair; review release notes before upgrading.
: "${LBC_VERSION:=v2.14.1}"
: "${LBC_CHART_VERSION:=1.14.0}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"
eksctl utils associate-iam-oidc-provider --cluster "$CLUSTER_NAME" --region "$AWS_REGION" --approve
POLICY_NAME="NetOps-${CLUSTER_NAME}-LoadBalancerController"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
curl -fsSL "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/${LBC_VERSION}/docs/install/iam_policy.json" -o "$TEMP_DIR/iam-policy.json"
if ! aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  aws iam create-policy --policy-name "$POLICY_NAME" --policy-document "file://$TEMP_DIR/iam-policy.json" >/dev/null
fi
# Existing policies are not silently updated; review policy diff before controller upgrades.
eksctl create iamserviceaccount --cluster "$CLUSTER_NAME" --region "$AWS_REGION"   --namespace kube-system --name aws-load-balancer-controller   --attach-policy-arn "$POLICY_ARN" --override-existing-serviceaccounts --approve
VPC_ID=$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" --query 'cluster.resourcesVpcConfig.vpcId' --output text)
# Current AWS guide lists Gateway API CRDs as a prerequisite for this controller version.
kubectl apply --server-side -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml
helm repo add eks https://aws.github.io/eks-charts
helm repo update eks
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller   -n kube-system --version "$LBC_CHART_VERSION" --set "clusterName=$CLUSTER_NAME"   --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller   --set "region=$AWS_REGION" --set "vpcId=$VPC_ID" --set "image.tag=$LBC_VERSION" --wait --timeout 5m
# Standard EKS managed nodes, not EKS Auto Mode. CSI add-on manages its own service account.
EBS_ROLE="NetOps-${CLUSTER_NAME}-EBSCSIRole"
eksctl create iamserviceaccount --cluster "$CLUSTER_NAME" --region "$AWS_REGION"   --namespace kube-system --name ebs-csi-controller-sa --role-only --role-name "$EBS_ROLE"   --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicyV2 --approve
if ! aws eks describe-addon --cluster-name "$CLUSTER_NAME" --region "$AWS_REGION" --addon-name aws-ebs-csi-driver >/dev/null 2>&1; then
  aws eks create-addon --cluster-name "$CLUSTER_NAME" --region "$AWS_REGION"     --addon-name aws-ebs-csi-driver --service-account-role-arn "arn:aws:iam::${ACCOUNT_ID}:role/$EBS_ROLE" >/dev/null
fi
aws eks wait addon-active --cluster-name "$CLUSTER_NAME" --region "$AWS_REGION" --addon-name aws-ebs-csi-driver
kubectl rollout status deployment/aws-load-balancer-controller -n kube-system --timeout=120s
kubectl rollout status deployment/ebs-csi-controller -n kube-system --timeout=120s
