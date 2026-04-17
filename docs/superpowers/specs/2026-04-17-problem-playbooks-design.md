# Problem Playbooks for Deep Agents Testing

**Date:** 2026-04-17
**Status:** Approved
**Scope:** Playbooks in `rhpds/agentic-aiops-plays` + job template provisioning in `ocp4_workload_aap2_tenant_config`

## Purpose

Create 8 realistic failure scenarios that exercise all 4 SRE subagents in the Athena Deep Agents pipeline. Each playbook looks like a legitimate ops task but contains a realistic failure. The agents must diagnose the root cause from the error output alone — job template names give no hints.

## Repos Affected

- `rhpds/agentic-aiops-plays` — playbook files
- `rhpds/deepagents-aiops` — `ocp4_workload_aap2_tenant_config` role (job templates, credentials, EE)

## Scenarios

### 1. Ping RHEL Admin

- **Playbook:** `ping.yml` (existing, no changes)
- **Job Template:** "Ping RHEL Admin"
- **Credential:** `admin-backdoor-key` (SSH key that doesn't match any authorized_keys)
- **Failure:** `Permission denied (publickey)`
- **Target subagent:** `sre_networking`
- **Kira area:** networking

### 2. Install Web Server

- **Playbook:** `install-webserver.yml`
- **Job Template:** "Install Web Server"
- **Credential:** `{{ guid }}-rhel-ssh`
- **Failure:** `dnf install apache` — package name is `httpd` on RHEL, not `apache`. Produces `No match for argument: apache`.
- **Target subagent:** `sre_linux`
- **Kira area:** linux

### 3. Start Web Server

- **Playbook:** `start-webserver.yml`
- **Job Template:** "Start Web Server"
- **Credential:** `{{ guid }}-rhel-ssh`
- **Failure:** `systemctl start httpd` — httpd not installed. Produces `Unit httpd.service not found`.
- **Target subagent:** `sre_linux`
- **Kira area:** linux

### 4. Deploy Payment Service

- **Playbook:** `deploy-app.yml`
- **Job Template:** "Deploy Payment Service"
- **Credential:** `{{ guid }}-openshift`
- **Hosts:** localhost (connection: local)
- **Failure:** Creates a Deployment with image `registry.internal.example.com/apps/payment-service:2.1.0` (doesn't exist). Pods go ImagePullBackOff. Playbook waits for rollout and times out.
- **Target subagent:** `sre_openshift`
- **Kira area:** kubernetes

### 5. Verify Service DNS

- **Playbook:** `check-dns.yml`
- **Job Template:** "Verify Service DNS"
- **Credential:** `{{ guid }}-rhel-ssh`
- **Failure:** `dig +short app.internal.example.com` returns empty (NXDOMAIN). Task uses `failed_when` to fail explicitly.
- **Target subagent:** `sre_networking`
- **Kira area:** networking

### 6. Deploy Monitoring Agent

- **Playbook:** `deploy-secure-app.yml`
- **Job Template:** "Deploy Monitoring Agent"
- **Credential:** `{{ guid }}-openshift`
- **Hosts:** localhost (connection: local)
- **Failure:** Creates a Pod requesting `privileged: true` and `runAsUser: 0` in the tenant namespace (restricted SCC). Fails with `unable to validate against any security context constraint`.
- **Target subagent:** `sre_openshift`
- **Kira area:** kubernetes

### 7. Update System Packages

- **Playbook:** `update-packages.yml`
- **Job Template:** "Update System Packages"
- **Credential:** `{{ guid }}-rhel-ssh`
- **Failure:** Configures a non-existent Satellite repo (`satellite.internal.example.com`), then runs `dnf update`. Fails on repo metadata fetch.
- **Target subagent:** `sre_linux`
- **Kira area:** linux

### 8. System Health Check

- **Playbook:** `run-health-check.yml`
- **Job Template:** "System Health Check"
- **Credential:** `{{ guid }}-rhel-ssh`
- **Execution Environment:** "Custom Health Check EE" (image `registry.internal.example.com/ee/health-check-ee:1.0` — doesn't exist)
- **Failure:** AAP2 can't pull the EE image. Job fails before the playbook executes.
- **Target subagent:** `sre_ansible`
- **Kira area:** application

## Playbook Content

### `ping.yml` (existing — no changes)

```yaml
---
- name: Ping RHEL VM
  hosts: all
  gather_facts: false
  tasks:
    - name: Ping the target host
      ansible.builtin.ping:
```

### `install-webserver.yml`

```yaml
---
- name: Install Web Server
  hosts: all
  become: true
  tasks:
    - name: Install web server package
      ansible.builtin.dnf:
        name: apache
        state: present
```

### `start-webserver.yml`

```yaml
---
- name: Start Web Server
  hosts: all
  become: true
  tasks:
    - name: Start and enable web server
      ansible.builtin.systemd:
        name: httpd
        state: started
        enabled: true
```

### `deploy-app.yml`

```yaml
---
- name: Deploy Payment Service
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Create deployment
      kubernetes.core.k8s:
        state: present
        definition:
          apiVersion: apps/v1
          kind: Deployment
          metadata:
            name: payment-service
            namespace: "{{ lookup('env', 'K8S_NAMESPACE') | default('default') }}"
          spec:
            replicas: 1
            selector:
              matchLabels:
                app: payment-service
            template:
              metadata:
                labels:
                  app: payment-service
              spec:
                containers:
                  - name: payment
                    image: registry.internal.example.com/apps/payment-service:2.1.0
                    ports:
                      - containerPort: 8080

    - name: Wait for rollout
      kubernetes.core.k8s_info:
        api_version: apps/v1
        kind: Deployment
        name: payment-service
        namespace: "{{ lookup('env', 'K8S_NAMESPACE') | default('default') }}"
      register: r_deploy
      retries: 6
      delay: 10
      until:
        - r_deploy.resources[0].status.readyReplicas is defined
        - r_deploy.resources[0].status.readyReplicas >= 1
      failed_when:
        - r_deploy.resources[0].status.readyReplicas is not defined
          or r_deploy.resources[0].status.readyReplicas < 1
```

### `check-dns.yml`

```yaml
---
- name: Verify Service DNS
  hosts: all
  gather_facts: false
  tasks:
    - name: Resolve application endpoint
      ansible.builtin.command:
        cmd: dig +short app.internal.example.com
      register: r_dns
      changed_when: false
      failed_when: r_dns.stdout | length == 0
```

### `deploy-secure-app.yml`

```yaml
---
- name: Deploy Monitoring Agent
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Deploy monitoring agent daemonset
      kubernetes.core.k8s:
        state: present
        definition:
          apiVersion: v1
          kind: Pod
          metadata:
            name: monitoring-agent
            namespace: "{{ lookup('env', 'K8S_NAMESPACE') | default('default') }}"
          spec:
            containers:
              - name: agent
                image: registry.redhat.io/openshift4/ose-prometheus-node-exporter:latest
                securityContext:
                  privileged: true
                  runAsUser: 0

    - name: Verify agent is running
      kubernetes.core.k8s_info:
        api_version: v1
        kind: Pod
        name: monitoring-agent
        namespace: "{{ lookup('env', 'K8S_NAMESPACE') | default('default') }}"
      register: r_pod
      retries: 6
      delay: 10
      until:
        - r_pod.resources | length > 0
        - r_pod.resources[0].status.phase == "Running"
```

### `update-packages.yml`

```yaml
---
- name: Update System Packages
  hosts: all
  become: true
  tasks:
    - name: Configure content source
      ansible.builtin.yum_repository:
        name: satellite-appstream
        description: Corporate Satellite - AppStream
        baseurl: https://satellite.internal.example.com/pulp/repos/prod/rhel9/appstream
        gpgcheck: false
        sslverify: false

    - name: Update all packages
      ansible.builtin.dnf:
        name: "*"
        state: latest
```

### `run-health-check.yml`

```yaml
---
- name: System Health Check
  hosts: all
  gather_facts: true
  tasks:
    - name: Check disk usage
      ansible.builtin.command:
        cmd: df -h /
      register: r_disk
      changed_when: false

    - name: Check memory
      ansible.builtin.command:
        cmd: free -m
      register: r_mem
      changed_when: false

    - name: Report health
      ansible.builtin.debug:
        msg: "Disk: {{ r_disk.stdout_lines[1] }} | Memory: {{ r_mem.stdout_lines[1] }}"
```

## AAP2 Tenant Config Changes

### New Credential: `admin-backdoor-key`

Machine credential with a valid-format RSA private key that doesn't match any authorized_keys on the RHEL VM. Created via `ansible.controller.credential` with credential_type "Machine" and ssh_key_data set to a generated key.

The key should be generated once and baked into the role as a static value (not generated per tenant) — the key is intentionally wrong, so it doesn't matter if it's shared.

### New Execution Environment: `Custom Health Check EE`

Created via `ansible.controller.execution_environment` pointing to image `registry.internal.example.com/ee/health-check-ee:1.0` (non-existent). Scoped to the tenant's organization.

### Job Templates (9 total including existing Ping RHEL VM)

| Job Template | Playbook | Credential | EE | Inventory |
|---|---|---|---|---|
| Ping RHEL VM | ping.yml | `{{ guid }}-rhel-ssh` | default | `{{ guid }}-inventory` |
| Ping RHEL Admin | ping.yml | `admin-backdoor-key` | default | `{{ guid }}-inventory` |
| Install Web Server | install-webserver.yml | `{{ guid }}-rhel-ssh` | default | `{{ guid }}-inventory` |
| Start Web Server | start-webserver.yml | `{{ guid }}-rhel-ssh` | default | `{{ guid }}-inventory` |
| Deploy Payment Service | deploy-app.yml | `{{ guid }}-openshift` | default | `{{ guid }}-inventory` |
| Verify Service DNS | check-dns.yml | `{{ guid }}-rhel-ssh` | default | `{{ guid }}-inventory` |
| Deploy Monitoring Agent | deploy-secure-app.yml | `{{ guid }}-openshift` | default | `{{ guid }}-inventory` |
| Update System Packages | update-packages.yml | `{{ guid }}-rhel-ssh` | default | `{{ guid }}-inventory` |
| System Health Check | run-health-check.yml | `{{ guid }}-rhel-ssh` | Custom Health Check EE | `{{ guid }}-inventory` |

### Webhook Coverage

The Athena role runs after `aap2_tenant_config` and attaches the webhook to all job templates in the org. All 9 templates get the webhook automatically.

## Subagent Coverage

| Subagent | Scenarios |
|---|---|
| `sre_networking` | Ping RHEL Admin, Verify Service DNS |
| `sre_linux` | Install Web Server, Start Web Server, Update System Packages |
| `sre_openshift` | Deploy Payment Service, Deploy Monitoring Agent |
| `sre_ansible` | System Health Check (broken EE) |

## Design Decisions

**Realistic names, no hints:** Job template names describe the intended operation, not the failure. The agents must diagnose from error output alone.

**Deterministic failures:** Every scenario fails reliably regardless of VM/cluster state. No dependency on specific pre-conditions beyond what the provisioning already guarantees.

**Static bad SSH key:** The `admin-backdoor-key` credential uses a fixed RSA key baked into the role. Since the key is intentionally wrong, sharing it across tenants is fine and avoids per-tenant key generation complexity.

**localhost for K8s playbooks:** OpenShift scenarios use `hosts: localhost` with `kubernetes.core.k8s` module and the OCP bearer token credential. No dependency on the RHEL VM.

**Existing `ping.yml` reused:** The "Ping RHEL Admin" template uses the same `ping.yml` playbook as "Ping RHEL VM" — the failure comes from the credential, not the playbook.
