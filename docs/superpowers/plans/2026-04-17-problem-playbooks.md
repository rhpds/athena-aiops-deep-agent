# Problem Playbooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create 8 failure-scenario playbooks and auto-provision 9 job templates so every SRE subagent in the Athena Deep Agents pipeline gets exercised.

**Architecture:** Playbooks live in `rhpds/agentic-aiops-plays`. Job templates, credentials, and EE are provisioned by the `ocp4_workload_aap2_tenant_config` role in `rhpds/deepagents-aiops`. The Athena role runs after and attaches webhooks to all templates automatically.

**Tech Stack:** Ansible playbooks (YAML), `ansible.controller` collection modules, `kubernetes.core` collection

**Spec:** `docs/superpowers/specs/2026-04-17-problem-playbooks-design.md`

**Repos:**
- Playbooks: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/`
- Collection: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/`

---

## File Structure

**agentic-aiops-plays repo** (7 new files):
```
install-webserver.yml
start-webserver.yml
deploy-app.yml
check-dns.yml
deploy-secure-app.yml
update-packages.yml
run-health-check.yml
```

**deepagents-aiops collection** (2 files modified):
```
roles/ocp4_workload_aap2_tenant_config/defaults/main.yml    — new variables
roles/ocp4_workload_aap2_tenant_config/tasks/workload.yml   — new credential, EE, job templates
```

---

### Task 1: Create All Playbooks

**Files:**
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/install-webserver.yml`
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/start-webserver.yml`
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/deploy-app.yml`
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/check-dns.yml`
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/deploy-secure-app.yml`
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/update-packages.yml`
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/run-health-check.yml`

- [ ] **Step 1: Create `install-webserver.yml`**

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

- [ ] **Step 2: Create `start-webserver.yml`**

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

- [ ] **Step 3: Create `deploy-app.yml`**

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

- [ ] **Step 4: Create `check-dns.yml`**

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

- [ ] **Step 5: Create `deploy-secure-app.yml`**

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

- [ ] **Step 6: Create `update-packages.yml`**

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

- [ ] **Step 7: Create `run-health-check.yml`**

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

- [ ] **Step 8: Validate YAML syntax for all playbooks**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays && ruby -ryaml -e 'Dir["*.yml"].each{|f| YAML.safe_load(File.read(f))}; puts "All YAML OK"'`

Expected: `All YAML OK`

- [ ] **Step 9: Commit and push**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays
git add install-webserver.yml start-webserver.yml deploy-app.yml check-dns.yml deploy-secure-app.yml update-packages.yml run-health-check.yml
git commit -m "feat: add 7 problem playbooks for Deep Agents testing

Each playbook simulates a realistic ops failure:
- install-webserver: wrong package name (apache vs httpd)
- start-webserver: service not installed
- deploy-app: bad container image (ImagePullBackOff)
- check-dns: NXDOMAIN on internal hostname
- deploy-secure-app: privileged pod in restricted namespace
- update-packages: non-existent Satellite repo
- run-health-check: valid playbook (failure comes from broken EE)"
git push
```

---

### Task 2: Add New Defaults for Credentials, EE, and Job Templates

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_aap2_tenant_config/defaults/main.yml`

- [ ] **Step 1: Generate a dummy SSH private key for the backdoor credential**

Run: `ssh-keygen -t rsa -b 2048 -f /tmp/athena-dummy-key -N "" -q && cat /tmp/athena-dummy-key && rm /tmp/athena-dummy-key /tmp/athena-dummy-key.pub`

Save the output — this is the static key to bake into the role defaults.

- [ ] **Step 2: Add new variables to defaults/main.yml**

Append the following after the existing `ocp4_workload_aap2_tenant_config_job_template_ping_name` line:

```yaml

# Backdoor credential (intentionally bad SSH key for testing)
ocp4_workload_aap2_tenant_config_backdoor_credential_name: admin-backdoor-key
ocp4_workload_aap2_tenant_config_backdoor_ssh_user: admin
ocp4_workload_aap2_tenant_config_backdoor_ssh_key: |
  <PASTE THE RSA KEY FROM STEP 1 HERE>

# Broken Execution Environment (intentionally unpullable image)
ocp4_workload_aap2_tenant_config_broken_ee_name: "Custom Health Check EE"
ocp4_workload_aap2_tenant_config_broken_ee_image: "registry.internal.example.com/ee/health-check-ee:1.0"

# Job template names
ocp4_workload_aap2_tenant_config_job_templates:
  - name: Ping RHEL VM
    playbook: ping.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_machine_credential_name }}"
  - name: Ping RHEL Admin
    playbook: ping.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_backdoor_credential_name }}"
  - name: Install Web Server
    playbook: install-webserver.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_machine_credential_name }}"
  - name: Start Web Server
    playbook: start-webserver.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_machine_credential_name }}"
  - name: Deploy Payment Service
    playbook: deploy-app.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_ocp_credential_name }}"
  - name: Verify Service DNS
    playbook: check-dns.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_machine_credential_name }}"
  - name: Deploy Monitoring Agent
    playbook: deploy-secure-app.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_ocp_credential_name }}"
  - name: Update System Packages
    playbook: update-packages.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_machine_credential_name }}"
  - name: System Health Check
    playbook: run-health-check.yml
    credential: "{{ ocp4_workload_aap2_tenant_config_machine_credential_name }}"
    execution_environment: "{{ ocp4_workload_aap2_tenant_config_broken_ee_name }}"
```

- [ ] **Step 3: Remove the old single job template variable**

Remove the line:
```yaml
ocp4_workload_aap2_tenant_config_job_template_ping_name: "Ping RHEL VM"
```

This is replaced by the `job_templates` list.

- [ ] **Step 4: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_aap2_tenant_config/defaults/main.yml
git commit -m "feat(aap2): add defaults for backdoor credential, broken EE, and 9 job templates"
```

---

### Task 3: Update workload.yml with New Resources and Job Template Loop

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_aap2_tenant_config/tasks/workload.yml`

- [ ] **Step 1: Add backdoor credential task after the existing OpenShift credential task (after line 124)**

Insert after the `Create OpenShift credential` task:

```yaml

- name: Create backdoor SSH key credential
  ansible.controller.credential:
    name: "{{ ocp4_workload_aap2_tenant_config_backdoor_credential_name }}"
    organization: "{{ ocp4_workload_aap2_tenant_config_org_name }}"
    credential_type: Machine
    inputs:
      username: "{{ ocp4_workload_aap2_tenant_config_backdoor_ssh_user }}"
      ssh_key_data: "{{ ocp4_workload_aap2_tenant_config_backdoor_ssh_key }}"
    state: present
    controller_host: "{{ _ocp4_workload_aap2_tenant_config_controller_host }}"
    controller_username: "{{ _ocp4_workload_aap2_tenant_config_controller_username }}"
    controller_password: "{{ _ocp4_workload_aap2_tenant_config_controller_password }}"
    validate_certs: "{{ ocp4_workload_aap2_tenant_config_validate_certs }}"
  no_log: true
```

- [ ] **Step 2: Add broken EE task after the project task (after line 165)**

Insert after the `Create project from plays repo` task:

```yaml

- name: Create broken execution environment
  ansible.controller.execution_environment:
    name: "{{ ocp4_workload_aap2_tenant_config_broken_ee_name }}"
    organization: "{{ ocp4_workload_aap2_tenant_config_org_name }}"
    image: "{{ ocp4_workload_aap2_tenant_config_broken_ee_image }}"
    pull: missing
    state: present
    controller_host: "{{ _ocp4_workload_aap2_tenant_config_controller_host }}"
    controller_username: "{{ _ocp4_workload_aap2_tenant_config_controller_username }}"
    controller_password: "{{ _ocp4_workload_aap2_tenant_config_controller_password }}"
    validate_certs: "{{ ocp4_workload_aap2_tenant_config_validate_certs }}"
```

- [ ] **Step 3: Replace the single job template task with a loop over all templates**

Replace the existing `Create Ping RHEL VM job template` task (lines 170-183) with:

```yaml
- name: Create job templates
  ansible.controller.job_template:
    name: "{{ jt_item.name }}"
    organization: "{{ ocp4_workload_aap2_tenant_config_org_name }}"
    project: "{{ ocp4_workload_aap2_tenant_config_project_name }}"
    inventory: "{{ ocp4_workload_aap2_tenant_config_inventory_name }}"
    playbook: "{{ jt_item.playbook }}"
    credentials:
      - "{{ jt_item.credential }}"
    execution_environment: "{{ jt_item.execution_environment | default(omit) }}"
    state: present
    controller_host: "{{ _ocp4_workload_aap2_tenant_config_controller_host }}"
    controller_username: "{{ _ocp4_workload_aap2_tenant_config_controller_username }}"
    controller_password: "{{ _ocp4_workload_aap2_tenant_config_controller_password }}"
    validate_certs: "{{ ocp4_workload_aap2_tenant_config_validate_certs }}"
  loop: "{{ ocp4_workload_aap2_tenant_config_job_templates }}"
  loop_control:
    loop_var: jt_item
    label: "{{ jt_item.name }}"
```

- [ ] **Step 4: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && ruby -ryaml -e 'YAML.safe_load(File.read("roles/ocp4_workload_aap2_tenant_config/tasks/workload.yml")); puts "YAML OK"'`

Expected: `YAML OK`

- [ ] **Step 5: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_aap2_tenant_config/tasks/workload.yml
git commit -m "feat(aap2): add backdoor credential, broken EE, and 9 job templates via loop"
```

---

### Task 4: Update remove_workload.yml for Cleanup

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_aap2_tenant_config/tasks/remove_workload.yml`

- [ ] **Step 1: Read the current remove_workload.yml**

Read: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_aap2_tenant_config/tasks/remove_workload.yml`

- [ ] **Step 2: Update job template removal to use the loop**

Replace the existing single job template removal with a loop over `ocp4_workload_aap2_tenant_config_job_templates`. Also add removal for the backdoor credential and broken EE. The removal should happen in reverse order: job templates first, then EE, then credentials.

The job template removal task should be:

```yaml
    - name: Remove job templates
      ansible.controller.job_template:
        name: "{{ jt_item.name }}"
        organization: "{{ ocp4_workload_aap2_tenant_config_org_name }}"
        state: absent
        controller_host: "{{ _ocp4_workload_aap2_tenant_config_controller_host }}"
        controller_username: "{{ _ocp4_workload_aap2_tenant_config_controller_username }}"
        controller_password: "{{ _ocp4_workload_aap2_tenant_config_controller_password }}"
        validate_certs: "{{ ocp4_workload_aap2_tenant_config_validate_certs }}"
      loop: "{{ ocp4_workload_aap2_tenant_config_job_templates }}"
      loop_control:
        loop_var: jt_item
        label: "{{ jt_item.name }}"
      ignore_errors: true
```

Add after the job template removal (before project removal):

```yaml
    - name: Remove broken execution environment
      ansible.controller.execution_environment:
        name: "{{ ocp4_workload_aap2_tenant_config_broken_ee_name }}"
        organization: "{{ ocp4_workload_aap2_tenant_config_org_name }}"
        state: absent
        controller_host: "{{ _ocp4_workload_aap2_tenant_config_controller_host }}"
        controller_username: "{{ _ocp4_workload_aap2_tenant_config_controller_username }}"
        controller_password: "{{ _ocp4_workload_aap2_tenant_config_controller_password }}"
        validate_certs: "{{ ocp4_workload_aap2_tenant_config_validate_certs }}"
      ignore_errors: true

    - name: Remove backdoor credential
      ansible.controller.credential:
        name: "{{ ocp4_workload_aap2_tenant_config_backdoor_credential_name }}"
        organization: "{{ ocp4_workload_aap2_tenant_config_org_name }}"
        credential_type: Machine
        state: absent
        controller_host: "{{ _ocp4_workload_aap2_tenant_config_controller_host }}"
        controller_username: "{{ _ocp4_workload_aap2_tenant_config_controller_username }}"
        controller_password: "{{ _ocp4_workload_aap2_tenant_config_controller_password }}"
        validate_certs: "{{ ocp4_workload_aap2_tenant_config_validate_certs }}"
      ignore_errors: true
```

- [ ] **Step 3: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && ruby -ryaml -e 'YAML.safe_load(File.read("roles/ocp4_workload_aap2_tenant_config/tasks/remove_workload.yml")); puts "YAML OK"'`

Expected: `YAML OK`

- [ ] **Step 4: Commit and push both repos**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_aap2_tenant_config/tasks/remove_workload.yml
git commit -m "feat(aap2): update removal tasks for new credentials, EE, and job templates"
git push
```

---

## Notes

**AgnosticV catalog:** No changes needed — the catalog already references the `aap2_tenant_config` role and the `agentic-aiops-plays` project. The new playbooks and job templates are picked up automatically.

**Webhook coverage:** The Athena role runs after `aap2_tenant_config` and attaches the webhook to ALL job templates in the org. The 9 templates get webhook coverage automatically.

**SSH key:** The dummy SSH key in Step 2.1 must be generated fresh and pasted into the defaults. It's a valid RSA key format but doesn't match any authorized_keys on the RHEL VM — SSH will reject it with `Permission denied (publickey)`.
