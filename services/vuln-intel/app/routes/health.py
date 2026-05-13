from fastapi import APIRouter, Depends, Request

from tip_auth import require_permission

router = APIRouter(tags=["meta"])


@router.get("/health/sources", dependencies=[Depends(require_permission("intelligence:read"))])
async def source_health(request: Request) -> dict:
    repo = request.app.state.source_health
    records = await repo.get_all()
    return {
        "sources": [
            {
                "name": r.source_name,
                "status": r.status,
                "consecutive_failures": r.consecutive_failures,
                "last_success_at": r.last_success_at,
                "last_failure_at": r.last_failure_at,
                "last_error": r.last_error,
            }
            for r in records
        ]
    }
