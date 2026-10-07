# Project 1 resume wording

**NetOps — Multi-Service Kubernetes Deployment**  
Python, React, PostgreSQL, Docker, Kubernetes, Helm; AWS EKS/ECR/ALB after deployment

## Accurate for the delivered implementation

Use these after reviewing the code and running it yourself. Do not list a skill
as hands-on experience merely because its configuration is included in this ZIP.

- Implemented a network-health dashboard with a React frontend, Python REST API and probe worker, persisting HTTP response times and status history in PostgreSQL.
- Created multi-stage Dockerfiles and a Docker Compose environment with non-root application containers, authenticated metric ingestion, and separate schema initialization.
- Authored Helm charts for Deployments, a PostgreSQL StatefulSet, Services and ALB Ingress, with health probes, rolling updates, resource limits and optional CPU autoscaling.

## Replace the third bullet after a successful AWS deployment

- Deployed three application services on AWS EKS using Helm and ECR, configuring ALB ingress, IRSA for cloud controllers, and encrypted EBS storage for PostgreSQL.

If you actually enable and verify autoscaling, a possible alternative is:

- Configured and verified CPU-based API autoscaling from 2 to 4 replicas, with readiness probes, rolling updates and PodDisruptionBudgets for stateless workloads.

## Optional measured bullet — fill only with your real evidence

- Measured [X] successful requests/s at [C] concurrent clients with [Y] ms p95 latency and [Z]% errors on [hardware/configuration] using a recorded HTTP read benchmark.

An image-size bullet may compare the frontend build-stage image and production
runtime stage ONLY if `measure-images.sh` has produced actual sizes:

- Reduced the frontend runtime image size by [X]% relative to its Node build-stage image by packaging compiled React assets in an Nginx runtime image.

Do not claim a fixed 35% reduction, production availability, enterprise-scale
traffic, Jenkins, Terraform, Java, or Prometheus/Grafana in Project 1. Keep three
strong bullets on the resume, supported by demo screenshots, scripts and results.
