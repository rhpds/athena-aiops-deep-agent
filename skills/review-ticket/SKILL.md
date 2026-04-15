# Review Ticket

Validate a ticket produced by an SRE specialist before submission.

## Checklist

1. **Title quality**: Is it specific? Reject generic titles like "Job failed" or "Error occurred". Good titles name what failed and why.
2. **Evidence present**: Does the description contain actual log lines or error messages? Reject descriptions that make claims without evidence.
3. **Confidence justified**: Is the confidence score consistent with the evidence? Flag scores > 80 that lack clear error messages. Flag scores < 40 that have clear error messages.
4. **Risk calibrated**: Does the risk level match the described impact? A non-prod failure shouldn't be "critical". A production outage shouldn't be "low".
5. **Actions actionable**: Are recommended actions specific? Reject vague advice like "check the configuration" without saying which configuration and what to check.
6. **Internal consistency**: Do the root cause, recommendations, and issues tell the same story? Flag contradictions.
7. **Completeness**: Are affected_systems populated? Are skills listed? Are issues created for each distinct problem?

## Output

Return one of:
- **approved**: The ticket meets quality standards. Optionally include amendments — specific field corrections to apply (e.g., "change confidence from 90 to 70 because the error message is ambiguous").
- **escalate**: The ticket does not meet quality standards. Include a specific reason (e.g., "description contains no evidence from logs — only assertions").
