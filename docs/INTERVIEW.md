# Explain this project in an interview

## A 45-second introduction

"I built NetOps, a small network-health dashboard with a React frontend, a Python
API and probe worker, and PostgreSQL. The worker sends real HTTP probes and stores
response times and status history through authenticated ingestion. I wrote
Dockerfiles and a Compose setup, then Helm charts for stateless Deployments,
a PostgreSQL StatefulSet, Services and ALB Ingress. I used separate liveness and
readiness checks so a database failure stops API traffic without forcing unnecessary
process restarts. I also included rolling updates and optional CPU autoscaling.
The database is single-instance because this is a learning lab."

Add your AWS deployment experience only AFTER you actually deploy it. Describe the
region/node configuration, controller IAM setup and incidents you personally
verified. Replace vague claims of optimization with a measured comparison.

## Questions and reasoning

**Why are API/frontend Deployments, but PostgreSQL a StatefulSet?**
API/frontend instances have no local durable state and can be replaced freely.
The StatefulSet gives PostgreSQL stable identity and an associated persistent
volume. Stable identity does not provide replication or failover.

**Why not store observations inside each API process?**
Multiple replicas would disagree and lose data on restart. Shared PostgreSQL
provides a consistent store. The SQLite mode exists only for offline tests.

**Why ALB plus Ingress?**
Ingress expresses HTTP routing in Kubernetes; AWS Load Balancer Controller
reconciles it into an ALB and supporting AWS resources. IP targets route to
frontend Pods. Nginx serves the React build and proxies API requests internally.

**Where does HTTPS terminate?**
At the ALB using an ACM certificate; the supplied internal path is HTTP. The
default restricted lab configuration uses HTTP unless a certificate is supplied.
A custom hostname needs DNS and a valid matching certificate.

**Why readiness and liveness differ?**
Readiness determines whether a Pod should receive traffic; the API requires its
database table. Liveness determines whether restarting the process is useful.
A database outage is not fixed by repeatedly restarting every API Pod.

**Why private nodes and public ALB subnets?**
The ALB accepts incoming traffic while nodes have no direct public IP exposure.
Private nodes use NAT for image/package access and controller AWS calls unless
endpoints replace those routes. The single NAT gateway is a lab cost/design
tradeoff and a potential availability dependency.

**How are credentials handled?**
Controllers use IAM roles for service accounts. Application Pods need no cloud
API permissions or AWS keys. Database credentials and the worker's ingestion token
are created outside Helm values/Git and loaded from a Kubernetes Secret. A Secret's
base64 representation is not an encryption guarantee.

**How do you scale?**
Stateless API replicas share the DB; an optional HPA targets CPU utilization relative
to requests. It needs metrics-server. This does not scale database capacity or add
nodes; more traffic may require connection pooling, database tuning and node scaling.

**What happens if a Pod dies?**
A Deployment creates a replacement; existing database data remains in PostgreSQL.
If PostgreSQL dies, the StatefulSet can attach the existing EBS volume to a
replacement Pod in that volume's zone, but service is interrupted.

**What measurements can you defend?**
Only results you have run and kept: endpoint, concurrency, successful requests/s,
latency percentiles, errors, hardware, image stage sizes, and resource samples.
Local SQLite test timing is not AWS throughput or PostgreSQL performance evidence.

**What would change for production?**
Use a redundant managed database and tested backups, audited secret management,
authenticated read access, deliberate network isolation, release/security scans,
full observability and SLOs, and tested failure/recovery behavior. The supplied
PDBs and replicas alone do not make the entire service highly available.

**Why no Jenkins/Terraform yet?**
This first project teaches application containers and Kubernetes deployment.
Project 2 will automate infrastructure and release workflow; Project 3 will
add monitoring and incident signals using the same application foundation.
