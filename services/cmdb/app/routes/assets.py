import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_common import ConflictError, NotFoundError

from app.db import get_session
from app.models import Asset
from app.schemas import AssetCreate, AssetList, AssetOut, AssetUpdate

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=AssetList, dependencies=[Depends(require_permission("assets:read"))])
async def list_assets(
    q: str | None = None,
    software: str | None = None,
    criticality: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> AssetList:
    stmt = select(Asset)
    if q:
        stmt = stmt.where(
            (Asset.hostname.ilike(f"%{q}%")) | (Asset.ip.ilike(f"%{q}%"))
        )
    if software:
        stmt = stmt.where(Asset.software.has_key(software))  # type: ignore[attr-defined]
    if criticality:
        stmt = stmt.where(Asset.criticality == criticality)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Asset.hostname).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return AssetList(items=[AssetOut.model_validate(r) for r in rows], total=total)


@router.post(
    "",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("assets:write"))],
)
async def create_asset(
    body: AssetCreate, session: AsyncSession = Depends(get_session)
) -> AssetOut:
    existing = await session.scalar(select(Asset).where(Asset.hostname == body.hostname))
    if existing:
        raise ConflictError(f"asset with hostname {body.hostname} already exists")
    asset = Asset(**body.model_dump())
    session.add(asset)
    await session.flush()
    return AssetOut.model_validate(asset)


@router.get(
    "/{asset_id}",
    response_model=AssetOut,
    dependencies=[Depends(require_permission("assets:read"))],
)
async def get_asset(asset_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> AssetOut:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError(f"asset {asset_id} not found")
    return AssetOut.model_validate(asset)


@router.patch(
    "/{asset_id}",
    response_model=AssetOut,
    dependencies=[Depends(require_permission("assets:write"))],
)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    session: AsyncSession = Depends(get_session),
) -> AssetOut:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError(f"asset {asset_id} not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    await session.flush()
    return AssetOut.model_validate(asset)


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("assets:delete"))],
)
async def delete_asset(
    asset_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError(f"asset {asset_id} not found")
    await session.delete(asset)


@router.post(
    "/bulk",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def bulk_import(
    file: UploadFile, session: AsyncSession = Depends(get_session)
) -> dict[str, int]:
    raw = (await file.read()).decode("utf-8")
    items: list[dict] = []
    if file.filename and file.filename.lower().endswith(".csv"):
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            row["tags"] = [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()]
            row["software"] = {}
            items.append(row)
    else:
        import json

        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("assets", [])

    created = 0
    updated = 0
    for item in items:
        existing = await session.scalar(
            select(Asset).where(Asset.hostname == item.get("hostname"))
        )
        if existing is None:
            session.add(Asset(**item))
            created += 1
        else:
            for k, v in item.items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
    await session.flush()
    return {"created": created, "updated": updated, "received": len(items)}
