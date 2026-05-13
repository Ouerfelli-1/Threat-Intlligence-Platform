from fastapi import APIRouter, Request

from app.schemas import SourceHealthOut

router = APIRouter(tags=["health"])


@router.get("/health/sources", response_model=list[SourceHealthOut])
async def source_health(request: Request):
    records = await request.app.state.source_health.get_all()
    return records
