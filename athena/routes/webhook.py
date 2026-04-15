"""AAP2 webhook receiver — POST /api/v1/webhook/aap2."""

import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response

from athena.services.ingestion import build_incident_envelope
from athena.services.submission import submit_ticket

router = APIRouter()
logger = logging.getLogger(__name__)


async def _process_webhook(job_id: int, app_state: dict):
    """Background task: ingest, analyze, submit."""
    from athena.agents.pipeline import run_pipeline

    try:
        envelope = await build_incident_envelope(app_state["aap2"], job_id=job_id)
        ticket_payload = await run_pipeline(envelope, app_state["settings"])
        await submit_ticket(
            payload=ticket_payload,
            kira=app_state["kira"],
            rocketchat=app_state["rocketchat"],
            kira_frontend_url=app_state["settings"].kira_url,
            rocketchat_channel=app_state["settings"].rocketchat_channel,
            job_name=envelope.job.name,
        )
        logger.info("Ticket created for job %s", job_id)
    except Exception:
        logger.exception("Pipeline failed for job %s", job_id)


@router.post("/api/v1/webhook/aap2", status_code=202)
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive AAP2 notification webhook and process asynchronously."""
    body = await request.json()

    # AAP2 webhook payload contains job ID in various formats
    job_id = body.get("id") or body.get("job", {}).get("id")
    if not job_id:
        return Response(content="Missing job ID in payload", status_code=400)

    background_tasks.add_task(_process_webhook, int(job_id), request.app.state._state)
    return {"status": "accepted", "job_id": job_id}
