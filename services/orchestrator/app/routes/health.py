from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health/sources")
async def source_health(request: Request):
    return await request.app.state.source_health.get_all()
