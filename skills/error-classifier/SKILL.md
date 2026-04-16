# Error Classifier

Classify the failure domain from an AAP2 job failure incident.

## Workflow

1. **Read** the error excerpt and stdout from the incident envelope
2. **Scan** for domain-specific signals:
   - **Ansible**: task/role/play references, module errors, collection not found, credential failures, "ansible" in paths, jinja2 template errors, variable undefined
   - **Linux**: dnf/yum errors, systemd unit failures, SELinux denials (avc:), permission denied on files, filesystem full/mount errors, kernel messages
   - **OpenShift/Kubernetes**: pod/container/image references, CrashLoopBackOff, ImagePullBackOff, RBAC denied, namespace/quota errors, operator errors, kubectl/oc output
   - **Networking**: DNS resolution failed, connection refused/timeout, SSH errors, TLS/SSL certificate errors, proxy errors, "unreachable" hosts, port binding failures
3. **Resolve** ambiguity: if signals span multiple domains, identify the root cause domain. Example: "Ansible task failed because DNS lookup timed out" → networking (not ansible)
4. **Emit** classification:
   - `domain`: one of ansible, linux, openshift, networking
   - `confidence`: 0-100 based on signal strength
   - `rationale`: one sentence explaining why this domain was chosen
