"""
TIP REST API — FastAPI application.

Provides a unified interface over all TIP modules:
  - Organizations (CRUD)
  - Assets, Vulnerabilities, Leaks, Alerts (read & update)
  - Risk dashboard
  - Manual sync trigger
"""
from typing import List, Optional
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tip.core.config import settings
from tip.core.database import create_all_tables, get_db
from tip.core.logger import get_logger
from tip.core.models import Alert, Asset, CVE, DataLeak, Organization

logger = get_logger(__name__)

# ── FastAPI app ──────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Unified Threat Intelligence Platform API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_all_tables()
    logger.info("TIP API started – tables ensured")


# ── Pydantic schemas ────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    primary_domain: str
    recon_scope_id: Optional[str] = None

class OrgOut(BaseModel):
    id: int
    name: str
    primary_domain: str
    recon_scope_id: Optional[str] = None
    class Config:
        from_attributes = True

class AssetOut(BaseModel):
    id: int
    asset_type: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    is_active: bool
    risk_score: float
    technologies: Optional[list] = None
    wazuh_agent_id: Optional[str] = None
    class Config:
        from_attributes = True

class CVEOut(BaseModel):
    id: int
    cve_id: str
    severity: Optional[str] = None
    cvss_v3_score: Optional[float] = None
    description: Optional[str] = None
    is_in_cisa_kev: bool = False
    has_exploit: bool = False
    class Config:
        from_attributes = True

class LeakOut(BaseModel):
    id: int
    leak_source: Optional[str] = None
    leak_type: Optional[str] = None
    severity: Optional[str] = None
    record_count: int = 0
    contains_passwords: bool = False
    contains_pii: bool = False
    status: str = "new"
    class Config:
        from_attributes = True

class AlertOut(BaseModel):
    id: int
    source_module: str
    alert_type: str
    severity: str
    priority: int
    title: str
    description: Optional[str] = None
    status: str
    asset_id: Optional[int] = None
    leak_id: Optional[int] = None
    cve_id: Optional[int] = None
    misp_event_id: Optional[str] = None
    opencti_report_id: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class AlertUpdate(BaseModel):
    status: Optional[str] = None   # open | acknowledged | resolved | false_positive
    assigned_to: Optional[str] = None

class RiskOut(BaseModel):
    organization: str
    domain: str
    risk_score: float
    risk_level: str
    metrics: dict

class SyncResponse(BaseModel):
    message: str
    assets_synced: int = 0
    cves_matched: int = 0
    leaks_found: int = 0
    alerts_generated: int = 0


# ── Health ───────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "tip-api"}


# ── Organizations ────────────────────────────────────────────────

@app.post("/api/v1/organizations", response_model=OrgOut, status_code=201)
def create_organization(body: OrgCreate, db: Session = Depends(get_db)):
    existing = db.query(Organization).filter(Organization.primary_domain == body.primary_domain).first()
    if existing:
        raise HTTPException(409, "Organization with this domain already exists")
    org = Organization(name=body.name, primary_domain=body.primary_domain, recon_scope_id=body.recon_scope_id)
    db.add(org)
    db.flush()
    return org

@app.get("/api/v1/organizations", response_model=List[OrgOut])
def list_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).all()

@app.get("/api/v1/organizations/{org_id}", response_model=OrgOut)
def get_organization(org_id: int, db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    return org

@app.delete("/api/v1/organizations/{org_id}", status_code=204)
def delete_organization(org_id: int, db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    db.delete(org)


# ── Assets ───────────────────────────────────────────────────────

@app.get("/api/v1/organizations/{org_id}/assets", response_model=List[AssetOut])
def list_assets(
    org_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    q = db.query(Asset).filter(Asset.organization_id == org_id)
    if active_only:
        q = q.filter(Asset.is_active.is_(True))
    return q.order_by(Asset.risk_score.desc()).all()


# ── Vulnerabilities ──────────────────────────────────────────────

@app.get("/api/v1/organizations/{org_id}/vulnerabilities", response_model=List[CVEOut])
def list_vulnerabilities(
    org_id: int,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    assets = db.query(Asset).filter(Asset.organization_id == org_id).all()
    cve_set = {}
    for a in assets:
        for c in a.vulnerabilities:
            if severity and c.severity != severity.upper():
                continue
            cve_set[c.id] = c
    return list(cve_set.values())


# ── Data Leaks ───────────────────────────────────────────────────

@app.get("/api/v1/organizations/{org_id}/leaks", response_model=List[LeakOut])
def list_leaks(org_id: int, db: Session = Depends(get_db)):
    return db.query(DataLeak).filter(DataLeak.organization_id == org_id).order_by(DataLeak.discovered_date.desc()).all()


# ── Alerts ───────────────────────────────────────────────────────

@app.get("/api/v1/alerts", response_model=List[AlertOut])
def list_all_alerts(
    severity: Optional[str] = None,
    source_module: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Alert)
    if severity:
        q = q.filter(Alert.severity == severity.upper())
    if source_module:
        q = q.filter(Alert.source_module == source_module)
    if status:
        q = q.filter(Alert.status == status)
    return q.order_by(Alert.created_at.desc()).limit(limit).all()

@app.get("/api/v1/organizations/{org_id}/alerts", response_model=List[AlertOut])
def list_org_alerts(
    org_id: int,
    severity: Optional[str] = None,
    source_module: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    # alerts linked to assets of this org
    asset_ids = [a.id for a in db.query(Asset).filter(Asset.organization_id == org_id).all()]
    leak_ids = [l.id for l in db.query(DataLeak).filter(DataLeak.organization_id == org_id).all()]

    q = db.query(Alert).filter(
        (Alert.asset_id.in_(asset_ids)) | (Alert.leak_id.in_(leak_ids))
    )
    if severity:
        q = q.filter(Alert.severity == severity.upper())
    if source_module:
        q = q.filter(Alert.source_module == source_module)
    return q.order_by(Alert.created_at.desc()).limit(limit).all()

@app.patch("/api/v1/alerts/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: int, body: AlertUpdate, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    if body.status:
        alert.status = body.status
    if body.assigned_to is not None:
        alert.assigned_to = body.assigned_to
    return alert


# ── Risk Dashboard ───────────────────────────────────────────────

@app.get("/api/v1/organizations/{org_id}/risk", response_model=RiskOut)
def get_org_risk(org_id: int, db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    from tip.correlation.engine import CorrelationEngine
    engine = CorrelationEngine(db)
    return engine.calculate_org_risk_score(org)


# ── Manual Sync Trigger ─────────────────────────────────────────

@app.post("/api/v1/organizations/{org_id}/sync", response_model=SyncResponse)
def trigger_sync(org_id: int, db: Session = Depends(get_db)):
    """Run the full pipeline: ASM sync → Software → CVE match → Leaks → Correlate."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    result = SyncResponse(message="Sync completed")

    # 1. ASM asset sync
    try:
        from tip.modules.asm.asset_service import AssetService
        asset_svc = AssetService(db)
        if org.recon_scope_id:
            synced = asset_svc.sync_assets_from_recon(org)
            result.assets_synced = len(synced)
    except Exception:
        logger.exception("ASM sync failed for org %d", org_id)

    # 2. Software sync from Wazuh (mocked)
    try:
        from tip.modules.asm.software_service import SoftwareService
        sw_svc = SoftwareService(db)
        sw_svc.sync_all_assets_for_org(org.id)
    except Exception:
        logger.exception("Software sync failed for org %d", org_id)

    # 3. CVE fetch + match
    try:
        from tip.modules.vuln_intel.cve_service import CVEService
        from tip.modules.vuln_intel.matching_service import MatchingService
        from tip.modules.vuln_intel.collectors.nvd_collector import NVDCollector
        collector = NVDCollector()
        raw_cves = collector.fetch_recent_cves(days=7)
        parsed = [collector.parse_cve(r) for r in raw_cves]
        cve_svc = CVEService(db)
        cve_svc.ingest_batch(parsed)
        new_cves = cve_svc.get_recent_cves(days=7)
        matcher = MatchingService(db)
        all_alerts = []
        for cve in new_cves:
            all_alerts.extend(matcher.scan_all_assets_for_cve(cve))
        result.cves_matched = len(all_alerts)
    except Exception:
        logger.exception("CVE matching failed for org %d", org_id)

    # 4. Leak check
    try:
        from tip.modules.data_leak.collectors.leak_collector import LeakCollector
        leak_collector = LeakCollector(db)
        leak_alerts = leak_collector.process_leaks(org)
        result.leaks_found = len(leak_alerts)
    except Exception:
        logger.exception("Leak check failed for org %d", org_id)

    # 5. Correlation
    try:
        from tip.correlation.engine import CorrelationEngine
        engine = CorrelationEngine(db)
        corr_alerts = engine.run_all(org)
        result.alerts_generated = len(corr_alerts)
    except Exception:
        logger.exception("Correlation failed for org %d", org_id)

    return result


# ── CVE Browse ───────────────────────────────────────────────────

@app.get("/api/v1/cves", response_model=List[CVEOut])
def list_cves(
    severity: Optional[str] = None,
    kev_only: bool = False,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(CVE)
    if severity:
        q = q.filter(CVE.severity == severity.upper())
    if kev_only:
        q = q.filter(CVE.is_in_cisa_kev.is_(True))
    return q.order_by(CVE.published_date.desc()).limit(limit).all()
