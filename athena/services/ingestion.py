"""Normalize AAP2 job data into an IncidentEnvelope.

Calls the AAP2 adapter to retrieve job metadata, stdout, and events,
then builds a validated IncidentEnvelope Pydantic model.
"""

import re
import uuid
from datetime import UTC, datetime

from athena.adapters.aap2 import AAP2Client
from athena.models import (
    EnvironmentContext,
    IncidentEnvelope,
    JobArtifacts,
    JobInfo,
)


def _extract_error_excerpt(stdout: str) -> str:
    """Pull the most relevant error lines from AAP2 job stdout."""
    lines = stdout.splitlines()
    error_lines = []
    for i, line in enumerate(lines):
        if re.search(r"fatal:|FAILED|ERROR|error:", line, re.IGNORECASE):
            # Grab the error line and up to 2 lines of context after
            error_lines.extend(lines[i : i + 3])
    if error_lines:
        return "\n".join(error_lines[:10])
    # Fallback: last 10 lines
    return "\n".join(lines[-10:])


async def build_incident_envelope(aap2: AAP2Client, job_id: int) -> IncidentEnvelope:
    """Fetch all job data from AAP2 and build an IncidentEnvelope."""
    job_data = await aap2.get_job(job_id)
    stdout = await aap2.get_job_stdout(job_id)
    events = await aap2.get_job_events(job_id)

    summary = job_data.get("summary_fields", {})
    jt = summary.get("job_template", {})
    ee = summary.get("execution_environment", {})

    job_info = JobInfo(
        id=str(job_data["id"]),
        name=job_data["name"],
        status="failed",
        template_id=str(jt.get("id", "")),
        template_name=jt.get("name", ""),
        project=summary.get("project", {}).get("name", ""),
        inventory=summary.get("inventory", {}).get("name", ""),
        execution_environment=ee.get("name", ""),
        started_at=job_data["started"],
        finished_at=job_data["finished"],
    )

    artifacts = JobArtifacts(
        stdout=stdout,
        error_excerpt=_extract_error_excerpt(stdout),
        events=events,
        playbook_path=job_data.get("playbook"),
        related_files=[],
    )

    context = EnvironmentContext(
        cluster=None,
        environment=None,
        namespace=None,
    )

    return IncidentEnvelope(
        event_id=str(uuid.uuid4()),
        received_at=datetime.now(UTC),
        source="aap2",
        job=job_info,
        artifacts=artifacts,
        context=context,
    )
