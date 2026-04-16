"""Manual analysis trigger — POST /api/v1/analyze."""

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from athena.agents.pipeline import run_pipeline
from athena.services.ingestion import build_incident_envelope
from athena.services.submission import submit_ticket

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    job_id: int


@router.post("/api/v1/analyze")
async def analyze_job(body: AnalyzeRequest, request: Request):
    """Manually trigger analysis of a specific failed AAP2 job.

    Runs the full pipeline synchronously and returns the ticket info.
    """
    s = request.app.state

    envelope = await build_incident_envelope(s.aap2, job_id=body.job_id)
    ticket_payload = await run_pipeline(envelope, s.settings)
    result = await submit_ticket(
        payload=ticket_payload,
        kira=s.kira,
        rocketchat=s.rocketchat,
        kira_frontend_url=s.settings.kira_url,
        rocketchat_channel=s.settings.rocketchat_channel,
        job_name=envelope.job.name,
    )

    return {
        "status": "completed",
        "job_id": body.job_id,
        "job_name": envelope.job.name,
        "ticket_id": result["ticket_id"],
        "ticket_url": result["ticket_url"],
        "area": ticket_payload.area,
        "risk": ticket_payload.risk,
        "confidence": ticket_payload.confidence,
    }
