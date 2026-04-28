"""AAP2 webhook receiver — POST /api/v1/webhook/aap2."""

import asyncio
import logging

from fastapi import APIRouter, Request, Response
from starlette.datastructures import State

from athena.services.ingestion import build_incident_envelope
from athena.services.submission import submit_ticket

router = APIRouter()
logger = logging.getLogger(__name__)

PIPELINE_MAX_RETRIES = 5
PIPELINE_RETRY_BASE_DELAY = 10  # seconds; backoff: 10, 20, 40, 80 (~2.5 min window)


async def _process_webhook(job_id: int, state: State):
    """Background task: ingest, analyze, submit — with retry on transient errors."""
    from athena.agents.pipeline import run_pipeline

    for attempt in range(1, PIPELINE_MAX_RETRIES + 1):
        try:
            envelope = await build_incident_envelope(state.aap2, job_id=job_id)
            ticket_payload = await run_pipeline(envelope, state.settings)
            await submit_ticket(
                payload=ticket_payload,
                kira=state.kira,
                rocketchat=state.rocketchat,
                kira_frontend_url=state.settings.kira_frontend_url or state.settings.kira_url,
                rocketchat_channel=state.settings.rocketchat_channel,
                job_name=envelope.job.name,
            )
            logger.info("Ticket created for job %s", job_id)
            return
        except Exception as exc:
            if attempt < PIPELINE_MAX_RETRIES:
                delay = PIPELINE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Pipeline attempt %d/%d failed for job %s (%s), retrying in %ds",
                    attempt,
                    PIPELINE_MAX_RETRIES,
                    job_id,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.exception(
                    "Pipeline failed for job %s after %d attempts",
                    job_id,
                    PIPELINE_MAX_RETRIES,
                )


@router.post("/api/v1/webhook/aap2", status_code=202)
async def receive_webhook(request: Request):
    """Receive AAP2 notification webhook and process asynchronously."""
    body = await request.json()

    # AAP2 webhook payload contains job ID in various formats
    job_id = body.get("id") or body.get("job", {}).get("id")
    if not job_id:
        return Response(content="Missing job ID in payload", status_code=400)

    task = asyncio.create_task(_process_webhook(int(job_id), request.app.state))
    request.app.state.active_pipelines.add(task)
    task.add_done_callback(request.app.state.active_pipelines.discard)
    return {"status": "accepted", "job_id": job_id}
