# Analyze Linux Failure

Deep analysis of AAP2 job failures caused by host-level Linux issues.

## Workflow

1. **Read** the full incident context: stdout, events, job metadata
2. **Identify** the Linux subsystem involved:
   - Package management (dnf/yum): repo access, dependency conflicts, missing packages, Satellite content view gaps
   - Service management (systemd): unit failed to start/enable, dependency issues, restart loops
   - SELinux: AVC denials, wrong context, boolean not set, policy missing
   - Filesystem: disk full, mount failures, permission denied, ownership wrong
   - User/group: missing user, incorrect group membership, home directory issues
3. **Determine root cause** by correlating the Ansible error output with the underlying Linux issue
4. **Assess risk and confidence** based on evidence
5. **Recommend** specific actions:
   - For package issues: exact package names, repo to enable, Satellite content view to update
   - For service issues: systemctl commands, unit file changes, dependency resolution
   - For SELinux: semanage/setsebool commands, context corrections
   - For filesystem: space cleanup, mount options, chown/chmod commands
6. **List** affected hosts from the job output
