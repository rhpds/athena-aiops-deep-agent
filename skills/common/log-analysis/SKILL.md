---
name: log-analysis
description: Shared skill for parsing Ansible/AAP2 job stdout
---

# Log Analysis

Shared skill for parsing Ansible/AAP2 job output. Use this before domain-specific analysis.

## Workflow

1. **Identify task boundaries**: Ansible stdout uses `TASK [name] ***` markers. Find the failing task.
2. **Extract the failing task**: Note the task name, the role it belongs to, and the play.
3. **Isolate the error**: Look for `fatal:`, `FAILED!`, `ERROR`, or `msg:` lines within the task output.
4. **Capture the error detail**: The JSON block after `=> ` contains structured error data (msg, rc, stderr, stdout).
5. **Note preceding warnings**: Lines with `[WARNING]` before the failure may provide context (e.g., deprecation, missing file).
6. **Identify patterns**: Multiple hosts failing the same task suggests an environmental issue. One host failing suggests a host-specific issue.
7. **Check for stack traces**: Python tracebacks indicate module bugs or environment issues. Note the exception type and message.

## AAP2 Stdout Structure

```
PLAY [play name] ***
TASK [Gathering Facts] ***
ok: [host1]
TASK [role : task name] ***
fatal: [host1]: FAILED! => {"changed": false, "msg": "error detail here", "rc": 1}
```

The most important information is in the `FAILED! => {...}` JSON block.
