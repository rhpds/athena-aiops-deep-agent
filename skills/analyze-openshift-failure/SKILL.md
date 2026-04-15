# Analyze OpenShift Failure

Deep analysis of AAP2 job failures caused by OpenShift/Kubernetes cluster issues.

## Workflow

1. **Read** the full incident context: stdout, events, job metadata
2. **Identify** the cluster component involved:
   - Pod lifecycle: CrashLoopBackOff, ImagePullBackOff, Pending, OOMKilled, Init container failures
   - Image/registry: pull errors, auth failures, image not found, registry unreachable
   - RBAC: forbidden, service account missing permissions, role binding gaps
   - Resources: quota exceeded, limit range violations, insufficient CPU/memory
   - Operators: CRD not found, operator degraded, subscription issues
   - Networking: route misconfiguration, service selector mismatch, ingress issues
3. **Determine root cause** from the Ansible k8s/oc module output and any kubectl/oc command results in the logs
4. **Assess risk and confidence** based on evidence
5. **Recommend** specific actions:
   - For pod issues: kubectl/oc commands to inspect, resource limit adjustments
   - For RBAC: exact role/rolebinding YAML to apply
   - For quota: resource quota adjustments or cleanup commands
   - For operators: subscription fixes, CRD installation commands
6. **List** affected namespaces, deployments, and pods from the output
