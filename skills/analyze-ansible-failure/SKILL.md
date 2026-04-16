# Analyze Ansible Failure

Deep analysis of AAP2 job failures caused by Ansible automation issues.

## Workflow

1. **Read** the full incident context: stdout, events, job template, playbook path
2. **Identify** the failing task:
   - Which play, role, and task failed?
   - What module was used?
   - What were the module arguments (if visible)?
3. **Classify** the sub-category:
   - Syntax error in playbook/role
   - Collection or module not found / not installed in EE
   - Credential or authentication failure (vault, machine credential, cloud credential)
   - Execution environment missing required packages or collections
   - Variable undefined or incorrectly resolved (hostvars, group_vars, extra_vars)
   - Job template parameter misconfiguration (wrong inventory, limit, tags)
4. **Determine root cause** with specific evidence from the logs
5. **Assess risk**: critical (production automation broken), high (degraded automation), medium (non-prod), low (cosmetic/warning)
6. **Assess confidence**: based on evidence clarity — explicit error messages = high, ambiguous logs = lower
7. **Recommend** specific actions: exact files to edit, collections to install, credentials to update, EE to rebuild
8. **List** affected systems by name from the inventory/job output
