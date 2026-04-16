# Create Ticket

Structure your analysis output as a TicketPayload for submission to Kira.

## Required Fields

1. **title**: Clear, concise (< 100 chars). Format: "<What failed>: <Why it failed>". Example: "Deploy Web App failed: missing httpd package in content view"
2. **description**: Include these sections:
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
7. **recommended_action**: Specific and actionable. Include exact commands, file paths, or config changes. Never say "investigate further" without specifying what to investigate.
8. **affected_systems**: List system names from the job output (hostnames, services, namespaces)
9. **skills**: List expertise areas needed to resolve (e.g., ["ansible", "linux"], ["kubernetes", "networking"])
10. **issues**: Create a sub-issue for each distinct problem found. Each has title, description, severity.
