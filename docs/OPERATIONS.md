# Demo, troubleshooting, and cleanup

Commands assume Helm release `lab` in namespace `netops`. Use a dedicated lab
cluster for disruptive exercises. Keep image tags, secret values and database
password consistent between upgrades.

## Check the whole path

```bash
kubectl get pods,svc,ingress,pvc -n netops
kubectl logs -n netops deployment/lab-netops-api --tail=50
kubectl logs -n netops deployment/lab-netops-worker --tail=50
kubectl get events -n netops --sort-by=.metadata.creationTimestamp
kubectl get jobs -n netops
```

Save a screenshot of fresh API/frontend observations and a second of the trend.
Record the actual running image tags and cluster/replica configuration with them.
Never include secrets in screenshots or logs committed to Git.

## Pod replacement and data persistence

Save an observation ID from `/api/history?target=api&limit=1`, then delete an API Pod:

```bash
POD=$(kubectl get pods -n netops -l component=api -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod -n netops "$POD"
kubectl rollout status -n netops deployment/lab-netops-api --timeout=180s
```

The Deployment replaces the Pod; compare the saved history ID after replacement.
This demonstrates shared storage surviving an API Pod restart. It does not prove
zero downtime; record actual request failures if making an availability claim.

To check the stateful volume in your disposable lab, record a history ID, delete
the PostgreSQL Pod, and wait for it to become ready:

```bash
kubectl delete pod -n netops lab-netops-postgres-0
kubectl wait -n netops --for=condition=Ready pod/lab-netops-postgres-0 --timeout=300s
```

The database is unavailable during replacement. The same EBS volume should attach
to the recreated Pod and the saved history should remain. If the original zone has
no available node, an EBS volume cannot move zones; node placement matters.

## Controlled unhealthy observation

With the API reachable directly through a temporary port-forward, scale the
frontend to zero. Do not use the frontend port-forward for this exercise:

```bash
# Terminal 1:
kubectl port-forward -n netops svc/lab-netops-api 8000:8000
# Terminal 2:
kubectl scale deployment/lab-netops-frontend -n netops --replicas=0
curl 'http://127.0.0.1:8000/api/targets'
# Restore after seeing the frontend observation become unhealthy:
kubectl scale deployment/lab-netops-frontend -n netops --replicas=2
kubectl rollout status deployment/lab-netops-frontend -n netops --timeout=180s
curl 'http://127.0.0.1:8000/api/targets'
```

The UI cannot be served while frontend replicas are zero; use direct API evidence
for the failure interval, then inspect the recovered UI history. The worker
records a connection failure with null HTTP status. Stop the port-forward after
the exercise. A normal Helm deployment restores declared replica configuration.

## Rollout and rollback

Build/push a new unique IMAGE_TAG, then run `scripts/deploy.sh` again with your
previous region, CIDRs and any TLS settings. The migration Job name uses the Helm
revision; SQL initialization is idempotent. The deploy command waits for ready
resources and jobs and rolls back on failure (`--atomic`). New versions should
preserve schema compatibility. A rollback does not undo database writes/schema.

```bash
helm history lab -n netops
# Substitute an actually successful revision from the history:
helm rollback lab REVISION -n netops --wait --timeout 15m
```

## Common failures

| Symptom | Checks and likely cause |
|---|---|
| Docker build cannot download packages | Registry access/proxy configuration; retry from an unrestricted machine |
| ImagePullBackOff | Wrong ECR URI/tag; wrong region; missing image; node ECR access; amd64/ARM mismatch |
| PVC Pending | EBS CSI role/add-on, StorageClass, available nodes/zones; WaitForFirstConsumer waits for scheduling |
| Migrate Job failing | Secret/password, DB Pod logs, disk permissions, DB DNS/connection; inspect Job events |
| API unready, liveness healthy | Database/table unavailable; inspect migration Job, DB password, network policy |
| ALB address missing | Controller IAM/CRDs, subnet tags, two ALB subnets in different AZs, controller logs |
| ALB inaccessible | Trusted CIDR/source IP, listener/cert/DNS, private/public subnet selection |
| Nginx 502 | API Service endpoints/readiness, API_UPSTREAM and DNS resolver; dynamic DNS refresh avoids stale startup resolution |
| Worker repeatedly submit_failed | Token mismatch, API readiness, API network policy; inspect API status logs without printing token |
| Old observation becomes Stale | Worker unavailable or stopped; configured interval too large for fixed 30s threshold |
| HPA shows unknown metrics | metrics-server absent/unhealthy or insufficient CPU requests; check kubectl top |
| DB auth fails after changing secret | Password in an existing DB is unchanged by initialization env vars |

Useful controller checks:

```bash
kubectl logs -n kube-system deployment/aws-load-balancer-controller --tail=100
kubectl get endpointslices -n netops
kubectl describe pvc -n netops
kubectl describe ingress -n netops
```

If enabling NetworkPolicy breaks metrics scraping later, add a scoped ingress
allowance for the Prometheus pods rather than disabling all isolation.

## Cleanup — costs continue until resources are removed

For your dedicated lab, record the database volume ID BEFORE uninstalling or
deleting the cluster. Back up data you want to retain. Deleting a Pod/PVC is not a
backup operation.

```bash
kubectl get pvc -n netops -o wide
# Copy the bound PV name from that output:
kubectl get pv YOUR_BOUND_PV -o jsonpath='{.spec.csi.volumeHandle}'
kubectl get ingress -n netops
```

1. Uninstall the application: `helm uninstall lab -n netops`. Keep the ALB
   controller running until the associated ALB, target group(s), and controller
   security groups have been removed. Verify in AWS EC2/Load Balancers. If deletion
   is stuck, inspect controller permissions/finalizers; do not bypass finalizers
   without understanding which cloud resources remain.
2. The StatefulSet PVC/Retain-policy EBS data can remain after uninstall. Confirm
   you no longer need the data, then delete the application PVC. Record its EBS
   volume ID and verify detachment before explicitly deleting that volume in EC2
   or with `aws ec2 delete-volume --volume-id VOLUME_ID --region "$AWS_REGION"`.
   Only delete the volume you recorded for this lab. Delete any lab-created
   snapshots separately if no longer needed; snapshots also incur storage charges.
3. Delete the dedicated cluster using `eksctl delete cluster --name "$CLUSTER_NAME"
   --region "$AWS_REGION" --wait`. This removes cluster-managed node groups and
   VPC/NAT resources through their stacks; confirm stack deletion succeeded.
4. Remove only this lab's `netops-api`, `netops-frontend`, and `netops-worker` ECR
   repositories if you no longer need their images. Check for any other users of
   those repositories before deleting them.
5. Check for retained CloudWatch log groups, EBS volumes/snapshots, public IPs,
   IAM policies/role stacks, and any partially-created CloudFormation stacks.
   Delete only dedicated lab resources; never delete shared controllers, CRDs,
   certificates, DNS zones or policies as a blanket cleanup action.
6. Confirm billing/resource inventory after cleanup. An empty Kubernetes namespace
   alone does not establish that AWS charges stopped.

Retain policy is intentional data protection and requires an explicit cleanup
decision. EKS deletion does not guarantee removal of all externally-created or
retained resources. There is no destructive cleanup script in this package.
