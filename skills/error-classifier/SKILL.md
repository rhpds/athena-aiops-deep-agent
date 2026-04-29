# Error Classifier

Classify the failure domain from an AAP2 job failure incident.

## Workflow

1. **Read** the error excerpt and stdout from the incident envelope
2. **Scan** for domain-specific signals:
   - **Ansible**: task/role/play references, module errors, collection not found, credential failures, "ansible" in paths, jinja2 template errors, variable undefined. NOT package manager failures — "No package X available" or dnf/yum errors are package_management even when surfaced by an Ansible task
   - **Linux**: systemd unit failures, SELinux denials (avc:), permission denied on files, filesystem full/mount errors, kernel messages
   - **Package Management**: dnf/yum errors, "No match for argument", "No package X available", missing or disabled repositories, Satellite content gaps, CRB/EPEL requirements, subscription-manager errors
   - **OpenShift/Kubernetes**: pod/container/image references, CrashLoopBackOff, ImagePullBackOff, RBAC denied, namespace/quota errors, operator errors, kubectl/oc output
   - **Networking**: DNS resolution failed, connection refused/timeout, SSH errors, TLS/SSL certificate errors, proxy errors, "unreachable" hosts, port binding failures
3. **Resolve** ambiguity: if signals span multiple domains, identify the root cause domain. Example: "Ansible task failed because DNS lookup timed out" → networking (not ansible). "Ansible task failed because package not found" → package_management (not ansible)
4. **Emit** classification:
   - `domain`: one of ansible, linux, package_management, openshift, networking
   - `delegate_to`: the exact subagent name to call — use this mapping:
     - ansible → `sre_ansible`
     - linux → `sre_linux`
     - package_management → `sre_package_management`
     - openshift → `sre_openshift`
     - networking → `sre_networking`
   - `confidence`: 0-100 based on signal strength
   - `rationale`: one sentence explaining why this domain was chosen
