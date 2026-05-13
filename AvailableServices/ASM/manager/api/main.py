"""
Recon Manager - REST API Endpoints
FastAPI implementation
"""

from fastapi import FastAPI, HTTPException, Depends, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models.schemas import (
    ScopeCreate, ScopeUpdate,
    TargetCreate, TargetUpdate,
    ScheduleCreate, ScheduleUpdate,
    PassiveFeatures, ActiveFeatures, ReconParameters,
    NmapConfig, CVEConfig,
    APIResponse, PaginatedResponse
)
from services.scope_service import ScopeService
from services.target_service import TargetService
from services.job_service import JobService
from services.schedule_service import ScheduleService
from database import get_db_session, engine
from database.models import Base

app = FastAPI(
    title="Recon Manager API",
    description="Orchestration and configuration API for recon engines",
    version="1.0.0"
)

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    """Create database tables on startup"""
    Base.metadata.create_all(bind=engine)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ==================== SCOPE ENDPOINTS ====================

@app.post("/api/v1/scopes", response_model=APIResponse, tags=["Scopes"])
async def create_scope(scope: ScopeCreate, db: Session = Depends(get_db_session)):
    """Create a new scope"""
    scope_service = ScopeService(db)
    existing = scope_service.get_scope_by_name(scope.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Scope '{scope.name}' already exists")
    
    new_scope = scope_service.create_scope(scope)
    
    return APIResponse(
        success=True,
        message="Scope created successfully",
        data={
            "id": new_scope.id,
            "name": new_scope.name,
            "description": new_scope.description,
            "enabled": new_scope.enabled,
            "created_at": str(new_scope.created_at)
        }
    )


@app.get("/api/v1/scopes", response_model=PaginatedResponse, tags=["Scopes"])
async def list_scopes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    enabled_only: bool = Query(False),
    db: Session = Depends(get_db_session)
):
    """List all scopes"""
    scope_service = ScopeService(db)
    skip = (page - 1) * page_size
    scopes = scope_service.list_scopes(skip=skip, limit=page_size, enabled_only=enabled_only)
    total = len(scopes)
    
    items = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "enabled": s.enabled,
            "created_at": str(s.created_at)
        }
        for s in scopes
    ]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0
    )


@app.get("/api/v1/scopes/{scope_id}", response_model=APIResponse, tags=["Scopes"])
async def get_scope(scope_id: str, db: Session = Depends(get_db_session)):
    """Get scope by ID"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    
    return APIResponse(
        success=True,
        data={
            "id": scope.id,
            "name": scope.name,
            "description": scope.description,
            "enabled": scope.enabled,
            "created_at": str(scope.created_at),
            "updated_at": str(scope.updated_at)
        }
    )


@app.patch("/api/v1/scopes/{scope_id}", response_model=APIResponse, tags=["Scopes"])
async def update_scope(scope_id: str, scope_update: ScopeUpdate, db: Session = Depends(get_db_session)):
    """Update scope"""
    scope_service = ScopeService(db)
    scope = scope_service.update_scope(scope_id, scope_update)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    
    return APIResponse(success=True, message="Scope updated", data={"id": scope.id, "enabled": scope.enabled})


@app.delete("/api/v1/scopes/{scope_id}", response_model=APIResponse, tags=["Scopes"])
async def delete_scope(scope_id: str, db: Session = Depends(get_db_session)):
    """Delete scope"""
    scope_service = ScopeService(db)
    success = scope_service.delete_scope(scope_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scope not found")
    return APIResponse(success=True, message="Scope deleted")


@app.post("/api/v1/scopes/{scope_id}/enable", response_model=APIResponse, tags=["Scopes"])
async def enable_scope(scope_id: str, db: Session = Depends(get_db_session)):
    """Enable a scope"""
    scope_service = ScopeService(db)
    scope = scope_service.enable_scope(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    return APIResponse(success=True, message="Scope enabled", data={"enabled": scope.enabled})


@app.post("/api/v1/scopes/{scope_id}/disable", response_model=APIResponse, tags=["Scopes"])
async def disable_scope(scope_id: str, db: Session = Depends(get_db_session)):
    """Disable a scope"""
    scope_service = ScopeService(db)
    scope = scope_service.disable_scope(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    return APIResponse(success=True, message="Scope disabled", data={"enabled": scope.enabled})


# ==================== TARGET ENDPOINTS ====================

@app.post("/api/v1/scopes/{scope_id}/targets", response_model=APIResponse, tags=["Targets"])
async def create_target(scope_id: str, target: TargetCreate, db: Session = Depends(get_db_session)):
    """Add target to scope"""
    target_service = TargetService(db)
    target.scope_id = scope_id
    new_target = target_service.create_target(target)
    
    return APIResponse(
        success=True,
        message="Target created",
        data={
            "id": new_target.id,
            "scope_id": new_target.scope_id,
            "type": new_target.type.value,
            "value": new_target.value,
            "enabled": new_target.enabled
        }
    )


@app.get("/api/v1/scopes/{scope_id}/targets", response_model=APIResponse, tags=["Targets"])
async def list_targets(scope_id: str, enabled_only: bool = Query(False), db: Session = Depends(get_db_session)):
    """List all targets in a scope"""
    target_service = TargetService(db)
    targets = target_service.list_targets(scope_id=scope_id, enabled_only=enabled_only)
    
    items = [
        {
            "id": t.id,
            "scope_id": t.scope_id,
            "type": t.type.value,
            "value": t.value,
            "enabled": t.enabled,
            "created_at": str(t.created_at)
        }
        for t in targets
    ]
    
    return APIResponse(success=True, data=items)


@app.patch("/api/v1/scopes/{scope_id}/targets/{target_id}", response_model=APIResponse, tags=["Targets"])
async def update_target(scope_id: str, target_id: str, target_update: TargetUpdate, db: Session = Depends(get_db_session)):
    """Update target"""
    target_service = TargetService(db)
    target = target_service.update_target(target_id, target_update)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return APIResponse(success=True, message="Target updated", data={"id": target.id, "enabled": target.enabled})


@app.delete("/api/v1/scopes/{scope_id}/targets/{target_id}", response_model=APIResponse, tags=["Targets"])
async def delete_target(scope_id: str, target_id: str, db: Session = Depends(get_db_session)):
    """Delete target"""
    target_service = TargetService(db)
    success = target_service.delete_target(target_id)
    if not success:
        raise HTTPException(status_code=404, detail="Target not found")
    return APIResponse(success=True, message="Target deleted")


# ==================== SCHEDULE ENDPOINTS ====================

@app.post("/api/v1/scopes/{scope_id}/schedules", response_model=APIResponse, tags=["Schedules"])
async def create_schedule(scope_id: str, schedule: ScheduleCreate, db: Session = Depends(get_db_session)):
    """Create a new schedule"""
    schedule_service = ScheduleService(db)
    schedule.scope_id = scope_id
    new_schedule = schedule_service.create_schedule(schedule)
    
    return APIResponse(
        success=True,
        message="Schedule created",
        data={
            "id": new_schedule.id,
            "scope_id": new_schedule.scope_id,
            "name": new_schedule.name,
            "cron_expression": new_schedule.cron_expression,
            "enabled": new_schedule.enabled
        }
    )


@app.get("/api/v1/scopes/{scope_id}/schedules", response_model=APIResponse, tags=["Schedules"])
async def list_schedules(scope_id: str, enabled_only: bool = Query(False), db: Session = Depends(get_db_session)):
    """List schedules for a scope"""
    schedule_service = ScheduleService(db)
    schedules = schedule_service.list_schedules(scope_id=scope_id, enabled_only=enabled_only)
    
    items = [
        {
            "id": s.id,
            "scope_id": s.scope_id,
            "name": s.name,
            "cron_expression": s.cron_expression,
            "enabled": s.enabled,
            "last_run": str(s.last_run) if s.last_run else None
        }
        for s in schedules
    ]
    
    return APIResponse(success=True, data=items)


@app.patch("/api/v1/scopes/{scope_id}/schedules/{schedule_id}", response_model=APIResponse, tags=["Schedules"])
async def update_schedule(scope_id: str, schedule_id: str, schedule_update: ScheduleUpdate, db: Session = Depends(get_db_session)):
    """Update schedule"""
    schedule_service = ScheduleService(db)
    schedule = schedule_service.update_schedule(schedule_id, schedule_update)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return APIResponse(success=True, message="Schedule updated", data={"id": schedule.id, "enabled": schedule.enabled})


@app.delete("/api/v1/scopes/{scope_id}/schedules/{schedule_id}", response_model=APIResponse, tags=["Schedules"])
async def delete_schedule(scope_id: str, schedule_id: str, db: Session = Depends(get_db_session)):
    """Delete schedule"""
    schedule_service = ScheduleService(db)
    success = schedule_service.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return APIResponse(success=True, message="Schedule deleted")


# ==================== FEATURE TOGGLE ENDPOINTS ====================

@app.get("/api/v1/scopes/{scope_id}/features/passive", response_model=APIResponse, tags=["Features"])
async def get_passive_features(scope_id: str, db: Session = Depends(get_db_session)):
    """Get passive recon feature toggles"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = scope.config or {}
    return APIResponse(success=True, data=config.get('passive_features', {}))


@app.patch("/api/v1/scopes/{scope_id}/features/passive", response_model=APIResponse, tags=["Features"])
async def update_passive_features(scope_id: str, features: PassiveFeatures, db: Session = Depends(get_db_session)):
    """Update passive recon features"""
    scope_service = ScopeService(db)
    updated = scope_service.update_passive_features(scope_id, features)
    if updated is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = updated.config or {}
    return APIResponse(success=True, message="Passive features updated", data=config.get('passive_features', {}))


@app.get("/api/v1/scopes/{scope_id}/features/active", response_model=APIResponse, tags=["Features"])
async def get_active_features(scope_id: str, db: Session = Depends(get_db_session)):
    """Get active recon feature toggles"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = scope.config or {}
    return APIResponse(success=True, data=config.get('active_features', {}))


@app.patch("/api/v1/scopes/{scope_id}/features/active", response_model=APIResponse, tags=["Features"])
async def update_active_features(scope_id: str, features: ActiveFeatures, db: Session = Depends(get_db_session)):
    """Update active recon features"""
    scope_service = ScopeService(db)
    updated = scope_service.update_active_features(scope_id, features)
    if updated is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = updated.config or {}
    return APIResponse(success=True, message="Active features updated", data=config.get('active_features', {}))


# ==================== PARAMETER ENDPOINTS ====================

@app.get("/api/v1/scopes/{scope_id}/parameters", response_model=APIResponse, tags=["Parameters"])
async def get_parameters(scope_id: str, db: Session = Depends(get_db_session)):
    """Get recon parameters for scope"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = scope.config or {}
    return APIResponse(success=True, data=config.get('parameters', {}))


@app.patch("/api/v1/scopes/{scope_id}/parameters", response_model=APIResponse, tags=["Parameters"])
async def update_parameters(scope_id: str, parameters: ReconParameters, db: Session = Depends(get_db_session)):
    """Update recon parameters"""
    scope_service = ScopeService(db)
    updated = scope_service.update_parameters(scope_id, parameters)
    if updated is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = updated.config or {}
    return APIResponse(success=True, message="Parameters updated", data=config.get('parameters', {}))


# ==================== NMAP CONFIGURATION ENDPOINTS ====================

@app.get("/api/v1/scopes/{scope_id}/config/nmap", response_model=APIResponse, tags=["Nmap"])
async def get_nmap_config(scope_id: str, db: Session = Depends(get_db_session)):
    """Get Nmap scanning configuration for scope"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = scope.config or {}
    nmap_config = config.get('nmap', {
        'enabled': True,
        'scan_type': 'default',
        'ports': None,
        'threads': 5,
        'timeout': 300,
        'check_cves': True
    })
    return APIResponse(success=True, data=nmap_config)


@app.patch("/api/v1/scopes/{scope_id}/config/nmap", response_model=APIResponse, tags=["Nmap"])
async def update_nmap_config(scope_id: str, nmap_config: NmapConfig, db: Session = Depends(get_db_session)):
    """Update Nmap scanning configuration"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    
    # Update config
    config = scope.config or {}
    config['nmap'] = nmap_config.dict()
    
    from models.schemas import ScopeUpdate
    scope_service.update_scope(scope_id, ScopeUpdate(config=config))
    
    return APIResponse(success=True, message="Nmap configuration updated", data=nmap_config.dict())


# ==================== CVE CONFIGURATION ENDPOINTS ====================

@app.get("/api/v1/scopes/{scope_id}/config/cve", response_model=APIResponse, tags=["CVE"])
async def get_cve_config(scope_id: str, db: Session = Depends(get_db_session)):
    """Get CVE lookup configuration for scope"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    config = scope.config or {}
    cve_config = config.get('cve', {
        'enabled': True,
        'nvd_api_key': None,
        'max_results_per_service': 20,
        'severity_threshold': None
    })
    # Don't expose API key in response
    if cve_config.get('nvd_api_key'):
        cve_config['nvd_api_key'] = '***configured***'
    return APIResponse(success=True, data=cve_config)


@app.patch("/api/v1/scopes/{scope_id}/config/cve", response_model=APIResponse, tags=["CVE"])
async def update_cve_config(scope_id: str, cve_config: CVEConfig, db: Session = Depends(get_db_session)):
    """Update CVE lookup configuration"""
    scope_service = ScopeService(db)
    scope = scope_service.get_scope(scope_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Scope not found")
    
    # Update config
    config = scope.config or {}
    config['cve'] = cve_config.dict()
    
    from models.schemas import ScopeUpdate
    scope_service.update_scope(scope_id, ScopeUpdate(config=config))
    
    response_data = cve_config.dict()
    if response_data.get('nvd_api_key'):
        response_data['nvd_api_key'] = '***configured***'
    
    return APIResponse(success=True, message="CVE configuration updated", data=response_data)


# ==================== JOB ENDPOINTS ====================

@app.post("/api/v1/jobs", response_model=APIResponse, tags=["Jobs"])
async def trigger_job(
    scope_id: str = Query(..., description="Scope ID"),
    mode: str = Query("passive", description="Recon mode: passive or active"),
    db: Session = Depends(get_db_session)
):
    """Manually trigger a recon job"""
    job_service = JobService(db)
    from models.schemas import JobCreate, ReconMode
    recon_mode = ReconMode.PASSIVE if mode == "passive" else ReconMode.ACTIVE
    job_data = JobCreate(scope_id=scope_id, mode=recon_mode, triggered_by="api")
    job = job_service.create_job(job_data)
    
    if not job:
        raise HTTPException(status_code=400, detail="Failed to create job")
    
    # Push job to Redis queue for engine to process
    import redis
    import json
    import os
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        r = redis.from_url(redis_url)
        job_payload = {
            "job_id": job.id,
            "scope_id": job.scope_id,
            "mode": job.mode.value,
            "triggered_by": job.triggered_by
        }
        r.lpush("recon_jobs", json.dumps(job_payload))
        print(f"Job {job.id} pushed to Redis queue")
    except Exception as e:
        print(f"Warning: Could not push to Redis ({redis_url}): {e}")
    
    return APIResponse(
        success=True,
        message="Job triggered",
        data={"job_id": job.id, "scope_id": job.scope_id, "mode": job.mode.value, "status": job.status.value}
    )


@app.get("/api/v1/jobs", response_model=PaginatedResponse, tags=["Jobs"])
async def list_jobs(
    scope_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db_session)
):
    """List jobs with filters"""
    job_service = JobService(db)
    skip = (page - 1) * page_size
    jobs = job_service.list_jobs(scope_id=scope_id, skip=skip, limit=page_size)
    
    items = [
        {
            "id": j.id,
            "scope_id": j.scope_id,
            "schedule_id": j.schedule_id,
            "mode": j.mode.value if j.mode else None,
            "status": j.status.value if j.status else None,
            "triggered_by": j.triggered_by,
            "created_at": str(j.created_at),
            "started_at": str(j.started_at) if j.started_at else None,
            "completed_at": str(j.completed_at) if j.completed_at else None,
            "findings_count": j.findings_count
        }
        for j in jobs
    ]
    
    total = len(items)
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0
    )


@app.get("/api/v1/jobs/{job_id}", response_model=APIResponse, tags=["Jobs"])
async def get_job(job_id: str, db: Session = Depends(get_db_session)):
    """Get job details"""
    job_service = JobService(db)
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return APIResponse(
        success=True,
        data={
            "id": job.id,
            "scope_id": job.scope_id,
            "schedule_id": job.schedule_id,
            "mode": job.mode.value if job.mode else None,
            "status": job.status.value if job.status else None,
            "triggered_by": job.triggered_by,
            "created_at": str(job.created_at),
            "started_at": str(job.started_at) if job.started_at else None,
            "completed_at": str(job.completed_at) if job.completed_at else None,
            "duration_seconds": job.duration_seconds,
            "targets_scanned": job.targets_scanned,
            "findings_count": job.findings_count,
            "errors_count": job.errors_count
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
