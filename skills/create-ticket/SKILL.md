# Create Ticket

Structure your analysis output as a TicketPayload for submission to Kira.

## Required Fields

1. **title**: Clear, concise (< 100 chars). Format: "<What failed>: <Why it failed>". Example: "Deploy Web App failed: missing httpd package in content view"
2. **description**: Include these sections separated by newlines (`\n`):
   - **Summary**: One paragraph explaining what happened
   - **Evidence**: Specific log lines, error messages, command output that support the diagnosis
   - **Root Cause**: What specifically caused the failure and why
   - **Impact**: What is affected and how severely
3. **area**: One of: linux, kubernetes, networking, application (use Kira's area values, not agent domain names)
4. **confidence**: 0-100. Justify it:
   - 80-100: Explicit error message directly identifies the cause
   - 60-79: Strong circumstantial evidence, likely cause
   - 40-59: Multiple possible causes, best guess
   - 0-39: Insufficient evidence, needs investigation
5. **risk**: Based on actual impact:
   - critical: Production service down or data loss
   - high: Production degraded or critical automation broken
   - medium: Non-production affected or limited impact
   - low: Cosmetic or informational
6. **stage**: dev, test, production, or unknown — based on the environment context
7. **recommended_action**: Specific and actionable. Use one numbered step per line, separated by newlines (`\n`). Include exact commands, file paths, or config changes. Never say "investigate further" without specifying what to investigate. Example format:
   ```
   1. Check the current password on the target host\n2. Update the AAP2 credential with the correct password\n3. Re-run the job to verify
   ```
8. **affected_systems**: List system names from the job output (hostnames, services, namespaces)
9. **skills**: List expertise areas needed to resolve (e.g., ["ansible", "linux"], ["kubernetes", "networking"])
10. **issues**: Create a sub-issue for each distinct problem found. Each has title, description, severity.
11. **agent_name**: REQUIRED. Your agent identifier exactly as defined in subagents.yaml (e.g., "sre_linux", "sre_openshift", "sre_networking", "sre_ansible", "sre_ssh"). Must be included in every TicketPayload.
