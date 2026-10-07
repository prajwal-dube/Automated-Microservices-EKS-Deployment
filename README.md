# Project 1 — NetOps: Multi-Service Deployment on AWS EKS

A working network-health dashboard with a React frontend, Python HTTP API,
Python probe worker, and PostgreSQL. Probes make actual HTTP requests and record
response time and status; the dashboard shows fresh health, recent latency
history, and stale observations. No invented performance results are included.

**Start locally first.** AWS deployment creates billable resources.

## What is included

| Component | Purpose |
|---|---|
| React + Nginx frontend | Polls API every 5s; inventory and last 30 latency observations |
| Python WSGI API + Gunicorn | Validates/authenticates ingestion and serves health/history |
| Python worker | Probes API and frontend every 10s; records HTTP failures and timeouts |
| PostgreSQL 16 | Shared data across API replicas; seven-day retention |
| Docker Compose | Full local environment with migration and dependency ordering |
| Helm chart | Deployments, StatefulSet, Services, ConfigMap, Job, Ingress, PDB, optional HPA/NetworkPolicy |
| EKS configuration + scripts | Private worker nodes, ALB controller, EBS CSI, ECR image builds/push |
| Tests and evidence tools | Offline API/worker tests, smoke test, HTTP benchmark, image-size comparison |

Python is the backend language for this project. Java is not used or claimed.
Terraform/Jenkins will be Project 2; Prometheus/Grafana will be Project 3.
This is a portfolio lab, with a single PostgreSQL instance and single NAT gateway.

## Verification delivered with this ZIP

Read `docs/VERIFICATION.md` and `results/verification.json` for the exact checks
run and skipped. The API and worker have been tested offline against SQLite and
real local HTTP servers. Docker images, React production build, Helm rendering,
PostgreSQL integration, and AWS deployment still require verification on your
machine. No AWS resources have been provisioned on your behalf.

## 1. Local setup — recommended first

Use Bash on Linux/macOS or WSL2 Ubuntu on Windows, Python 3.10+, and Docker Desktop
with Linux containers and Compose v2. Docker Desktop must be running; on Windows,
enable its WSL integration. Docker builds need outbound package-registry access.

From this project folder:

```bash
python3 scripts/create-secrets.py --compose
# Optional: generate and commit the frontend lockfile for repeatable dependency resolution.
# This needs Node.js 22+ installed locally; Docker itself includes Node for builds.
cd frontend
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
cd ..

docker compose up --build -d
python3 scripts/smoke.py --url http://127.0.0.1:8080
```

Open **http://127.0.0.1:8080**. Within roughly one probe interval, API and frontend
observations should appear. If image builds take time, the smoke timer starts
after the compose command returns. Watch logs if the smoke check times out.

```bash
docker compose ps
docker compose logs --tail=100 api worker frontend migrate
curl http://127.0.0.1:8000/readyz
curl http://127.0.0.1:8080/api/targets
```

There is no dependency on external APIs or API keys. Database and API are reached
through Compose service DNS. The database has no host port. Host API/UI ports are
bound to loopback. `.env` is ignored by Git; do not publish its contents.

```bash
# Stop services while retaining your database:
docker compose down
# Explicitly discard local database data when finished:
docker compose down -v
```

Do not change DB_PASSWORD after initializing the existing database volume without
also updating the password inside PostgreSQL. The image initialization variables
only apply on first startup of an empty volume.

## 2. Offline Python verification — Docker not required

```bash
bash scripts/check.sh
```

Tests use the standard library; no pip install is needed. This validates API
behavior and worker requests. It does not validate PostgreSQL or containers.
The script also checks shell syntax and runs Helm checks when Helm is installed.

For an offline API demo, start a terminal in the `api` directory:

```bash
export SQLITE_PATH=/tmp/netops-demo.db
export INGEST_TOKEN=offline-demo-token
python3 -m app.dev
```

In another terminal, from the project root:

```bash
export API_URL=http://127.0.0.1:8000
export INGEST_TOKEN=offline-demo-token
export PROBE_TARGETS='[{"name":"api","url":"http://127.0.0.1:8000/readyz"}]'
python3 worker/probe.py
```

Check `http://127.0.0.1:8000/api/targets`. To run the React development frontend,
install Node.js 22+, run `npm install` inside `frontend`, then `npm run dev` and
open the printed URL. Vite proxies `/api` to the offline API. The WSGI development
server is for local use only; containers use Gunicorn.

## 3. AWS prerequisites and cost controls

Install AWS CLI v2, a current `eksctl`, Helm 3, kubectl compatible with your chosen
cluster version, Docker, Python, and curl. Configure AWS access using SSO or your
normal credential chain. Never put AWS access keys into the application,
Dockerfiles, Helm values, or Git.

The scripts default to **ap-south-1**, cluster **netops-lab**, and EKS **1.35**.
Check availability/support in your AWS region before starting. This project uses
standard EKS managed EC2 nodes, not EKS Auto Mode. Your provisioning identity needs
permission to manage CloudFormation, EKS, VPC/EC2 resources, IAM roles/policies,
ECR, and load-balancer infrastructure. The application pods need no AWS IAM role.
AWS's controllers use IRSA roles for their specific purposes.

Review the AWS pricing calculator and create a budget before provisioning. EKS
control plane, two EC2 nodes, a NAT gateway, ALB, public IPv4, EBS, CloudWatch logs,
ECR storage, and data transfer can incur charges. Stopping your laptop does not
stop them. Use a dedicated lab account if available and follow the cleanup guide.
No fixed price or free-tier eligibility is assumed.

## 4. Create EKS, controllers, and database storage

Copy `deploy/eks/cluster.yaml` to `deploy/eks/cluster.local.yaml` and replace
`YOUR_PUBLIC_IP/32` with the public IPv4 address of the machine running kubectl.
A changed public IP requires updating EKS endpoint access. Prefer your actual
trusted /32 rather than opening the endpoint to all addresses.

```bash
export AWS_REGION=ap-south-1
export CLUSTER_NAME=netops-lab
aws sts get-caller-identity
bash scripts/create-cluster.sh deploy/eks/cluster.local.yaml
bash scripts/install-addons.sh
kubectl get nodes
kubectl get pods -n kube-system
```

The add-on script installs a documented matched ALB controller/chart pair and
Gateway API CRDs, plus the EBS CSI managed add-on with its IAM role. Although this
application uses Ingress, the AWS controller installation guide lists the
Gateway API CRDs as a prerequisite. The Helm chart creates an encrypted gp3
StorageClass with delayed volume binding. It retains EBS data on deletion.

The add-on script is for initial setup and a same-version install. When upgrading
a controller, review IAM policy changes and update CRDs using that release's
instructions. Do not assume `helm upgrade` upgrades CRDs. If an IAM role stack or
CSI add-on already exists, inspect its attached policy/role and use the AWS
upgrade instructions rather than deleting shared infrastructure.

## 5. Build and push your three application images

Use a unique image tag, preferably the Git commit SHA. The script builds amd64
images, matching the supplied t3.medium nodes, even on ARM developer machines.

```bash
export IMAGE_TAG=project1-v1
bash scripts/build-push.sh
```

ECR repositories have immutable tags and scan-on-push enabled. A repeated push
with an already-used tag fails; choose a new tag. Review scan results in ECR.
Pin base images by digest after checking them if you need fully reproducible
builds. Direct application versions are pinned; commit generated lockfiles and
refresh/test dependencies deliberately rather than using floating app versions.

## 6. Create credentials and deploy

```bash
python3 scripts/create-secrets.py
export TRUSTED_CIDRS=YOUR_PUBLIC_IPV4/32
bash scripts/deploy.sh
```

The secret script prompts for a database password of at least 16 characters and
generates a random ingestion token. It creates `netops-secrets` via stdin so
credentials are not in shell arguments or Helm release values. Retain your DB
password securely. Kubernetes Secrets use base64 encoding; that alone is not
encryption. Restrict RBAC and use your organization's secret-management practices
for production. The API authenticates worker ingestion with a shared bearer token;
reads are unauthenticated and ALB access is restricted to TRUSTED_CIDRS.

The default ingress is HTTP, suitable for a restricted learning demo. For HTTPS,
request/validate an ACM certificate in the same AWS region and supply a hostname:

```bash
export ACM_CERTIFICATE_ARN=arn:aws:acm:ap-south-1:ACCOUNT_ID:certificate/CERTIFICATE_ID
export DASHBOARD_HOST=netops.your-domain.example
bash scripts/deploy.sh
```

Create a DNS record for DASHBOARD_HOST pointing to the generated ALB. TLS
terminates at the ALB, with HTTP to Nginx inside the VPC. HTTPS configuration
redirects port 80 to 443. A custom ACM certificate does not cover the default
AWS ALB DNS name.

```bash
kubectl get ingress -n netops
kubectl get pods,svc,pvc -n netops
# HTTP-only configuration: use the ADDRESS from kubectl get ingress.
python3 scripts/smoke.py --url http://YOUR_ALB_DNS_NAME
# HTTPS configuration: use your certificate-covered custom hostname.
python3 scripts/smoke.py --url https://netops.your-domain.example
```

The URL must be accessible from your trusted source IP. If you prefer local
access without the ALB, use a port-forward:

```bash
kubectl port-forward -n netops svc/lab-netops-frontend 8080:8080
```

Run `scripts/check.sh` with Helm installed before deployment. You can also render
and validate against your connected cluster without creating workloads:

```bash
helm template lab deploy/helm/netops -n netops   --set ingress.inboundCidrs=YOUR_PUBLIC_IPV4/32 > /tmp/netops-rendered.yaml
kubectl apply --dry-run=server -f /tmp/netops-rendered.yaml -n netops
```

## 7. Optional CPU autoscaling and pod ingress isolation

HPA is supplied but disabled by default. It needs metrics-server. Install the
EKS-compatible metrics-server add-on, or follow its official installation guide;
verify `kubectl top pods -n netops` works. Enable HPA in an override file or with
Helm `--set hpa.enabled=true`, preserving the SAME ECR image values and ingress
values from your last successful deployment. It scales the API from two to four
replicas at 70% of requested CPU. This is not node autoscaling; enough node capacity
must already exist. API requests have CPU/memory requests and limits.

NetworkPolicies are disabled by default. Enable an enforcing engine (for example,
EKS VPC CNI network policy support), then enable `networkPolicy.enabled=true` in
Helm using the same deployment values. The policies limit ingress to PostgreSQL
and the API; they do not provide namespace-wide egress isolation. Future
Prometheus scrapers will need an explicit policy allowance. Check database
connectivity and probe submissions after enabling them.

PDBs protect against certain voluntary disruptions; they do not prevent crashes
or create database redundancy. Topology spreading is best effort. A worker
Recreate deployment avoids duplicate probes during updates; it has a brief gap.

## 8. Demonstrate updates, failures, and measured results

Read `docs/OPERATIONS.md` for pod replacement, controlled frontend outage,
rolling updates, persistence verification, rollback, and cleanup.
Read `docs/BENCHMARKS.md` before making performance or image-size claims.
Resume bullets are in `RESUME_POINTS.md`; interview explanations are in
`docs/INTERVIEW.md`.

```bash
python3 scripts/benchmark.py --url http://127.0.0.1:8080/api/targets   --requests 500 --concurrency 10
bash scripts/measure-images.sh
```

Benchmarks record observed outcomes under your conditions. There is no promised
throughput, latency reduction, or image-size reduction percentage.

## Reference documentation

- [AWS: install ALB controller with Helm](https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html)
- [AWS: ALB ingress routing](https://docs.aws.amazon.com/eks/latest/userguide/alb-ingress.html)
- [AWS: EBS CSI storage](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)
- [AWS: supported Kubernetes versions](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)
- [Kubernetes: probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/)
- [Kubernetes: HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Gateway API v1.4.0 release](https://github.com/kubernetes-sigs/gateway-api/releases/tag/v1.4.0)

These references informed the deployment configuration. Version support and
release prerequisites must still be checked when you deploy.

## Resume Points 

-- Automated Microservices & Network-Health Dashboard Deployment

Technologies: Kubernetes (AWS EKS), Docker, Helm, Python, React, PostgreSQL, ALB Ingress, Git

- Engineered a full-stack network-health dashboard using React, Python microservices, and PostgreSQL to actively track real-time HTTP/HTTPS response times and system metrics.
- Containerized multi-stack applications by creating multi-stage Dockerfiles and Docker Compose environments, enforcing container security via non-root execution and authenticated data ingestion.
- Authored production-ready Helm charts to orchestrate Kubernetes Deployments, StatefulSets, and Services on an AWS EKS cluster.
- Configured advanced cluster networking and traffic optimization using AWS Application Load Balancer (ALB) Ingress, integrating custom liveness/readiness health probes and horizontal pod autoscaling.


