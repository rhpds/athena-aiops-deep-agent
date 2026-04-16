"""Health check endpoints for Kubernetes probes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# Set by app lifespan once AAP2 connection is verified and webhook registered
_ready = False


def set_ready(ready: bool):
    global _ready
    _ready = ready


@router.get("/healthz")
async def healthz():
    """Liveness probe — always returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Readiness probe — returns 200 only when AAP2 webhook is registered."""
    if _ready:
        return {"status": "ready"}
    return JSONResponse(content={"status": "not ready"}, status_code=503)
