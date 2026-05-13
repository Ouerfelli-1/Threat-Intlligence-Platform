"""
Findings API - Separate service for querying recon results
FastAPI implementation
"""

import os
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from contextlib import contextmanager

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://recon:changeme@database:5432/recon_manager")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(
    title="Findings API",
    description="Query API for recon findings and results",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def get_connection():
    """Get database connection"""
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "findings-api", "timestamp": datetime.utcnow().isoformat()}


# ==================== SUMMARY ENDPOINTS ====================

@app.get("/api/v1/summary", tags=["Summary"])
async def get_results_summary():
    """Get overall summary of all findings"""
    with get_connection() as conn:
        # Total findings by type
        findings_by_type = conn.execute(text("""
            SELECT finding_type, COUNT(*) as count 
            FROM recon_findings 
            GROUP BY finding_type 
            ORDER BY count DESC
        """)).fetchall()
        
        # Total scopes with findings
        scopes_with_findings = conn.execute(text("""
            SELECT COUNT(DISTINCT scope_id) FROM recon_findings
        """)).scalar()
        
        # Total jobs with findings
        jobs_with_findings = conn.execute(text("""
            SELECT COUNT(DISTINCT job_id) FROM recon_findings
        """)).scalar()
        
        # Total unique subdomains
        unique_subdomains = conn.execute(text("""
            SELECT COUNT(DISTINCT value) FROM recon_findings WHERE finding_type = 'subdomain'
        """)).scalar()
        
        # Recent findings (last 24h)
        recent_findings = conn.execute(text("""
            SELECT COUNT(*) FROM recon_findings WHERE time > NOW() - INTERVAL '24 hours'
        """)).scalar()
    
    return {
        "total_findings": sum(row[1] for row in findings_by_type),
        "findings_by_type": {row[0]: row[1] for row in findings_by_type},
        "scopes_with_findings": scopes_with_findings,
        "jobs_with_findings": jobs_with_findings,
        "unique_subdomains": unique_subdomains,
        "findings_last_24h": recent_findings
    }


@app.get("/api/v1/stats/scopes", tags=["Stats"])
async def get_all_scopes_stats():
    """Get statistics for all scopes"""
    with get_connection() as conn:
        stats = conn.execute(text("""
            SELECT 
                s.id,
                s.name,
                s.enabled,
                COUNT(DISTINCT j.id) as total_jobs,
                COUNT(DISTINCT CASE WHEN j.status = 'COMPLETED' THEN j.id END) as completed_jobs,
                COUNT(DISTINCT rf.id) as total_findings,
                COUNT(DISTINCT CASE WHEN rf.finding_type = 'subdomain' THEN rf.value END) as unique_subdomains,
                MAX(j.created_at) as last_job
            FROM scopes s
            LEFT JOIN jobs j ON s.id = j.scope_id
            LEFT JOIN recon_findings rf ON s.id = rf.scope_id
            GROUP BY s.id, s.name, s.enabled
            ORDER BY s.name
        """)).fetchall()
    
    return {
        "scopes": [
            {
                "id": s[0],
                "name": s[1],
                "enabled": s[2],
                "total_jobs": s[3],
                "completed_jobs": s[4],
                "total_findings": s[5],
                "unique_subdomains": s[6],
                "last_job": str(s[7]) if s[7] else None
            }
            for s in stats
        ]
    }


# ==================== SCOPE FINDINGS ENDPOINTS ====================

@app.get("/api/v1/scopes/{scope_id}/findings", tags=["Scope Findings"])
async def get_scope_findings(
    scope_id: str,
    finding_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    """Get all findings for a specific scope"""
    offset = (page - 1) * page_size
    
    with get_connection() as conn:
        # Build query
        where_clause = "WHERE scope_id = :scope_id"
        params = {"scope_id": scope_id, "limit": page_size, "offset": offset}
        
        if finding_type:
            where_clause += " AND finding_type = :finding_type"
            params["finding_type"] = finding_type
        
        # Get findings
        findings = conn.execute(text(f"""
            SELECT id, finding_type, value, source, time, job_id, extra_data
            FROM recon_findings 
            {where_clause}
            ORDER BY time DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()
        
        # Get total count
        total = conn.execute(text(f"""
            SELECT COUNT(*) FROM recon_findings {where_clause}
        """), params).scalar()
        
        # Get scope name
        scope = conn.execute(text("SELECT name FROM scopes WHERE id = :id"), {"id": scope_id}).fetchone()
    
    return {
        "scope_id": scope_id,
        "scope_name": scope[0] if scope else None,
        "total": total,
        "page": page,
        "page_size": page_size,
        "findings": [
            {
                "id": f[0],
                "finding_type": f[1],
                "value": f[2],
                "source": f[3],
                "discovered_at": str(f[4]),
                "job_id": f[5],
                "extra_data": f[6]
            }
            for f in findings
        ]
    }


@app.get("/api/v1/scopes/{scope_id}/summary", tags=["Scope Findings"])
async def get_scope_summary(scope_id: str):
    """Get summary statistics for a specific scope"""
    with get_connection() as conn:
        # Findings by type
        findings_by_type = conn.execute(text("""
            SELECT finding_type, COUNT(*) as count 
            FROM recon_findings 
            WHERE scope_id = :scope_id
            GROUP BY finding_type
        """), {"scope_id": scope_id}).fetchall()
        
        # Jobs for this scope
        jobs = conn.execute(text("""
            SELECT id, status, findings_count, created_at, completed_at
            FROM jobs 
            WHERE scope_id = :scope_id
            ORDER BY created_at DESC
            LIMIT 10
        """), {"scope_id": scope_id}).fetchall()
        
        # Unique subdomains
        subdomains = conn.execute(text("""
            SELECT COUNT(DISTINCT value) FROM recon_findings 
            WHERE scope_id = :scope_id AND finding_type = 'subdomain'
        """), {"scope_id": scope_id}).scalar()
        
        # Scope info
        scope = conn.execute(text("""
            SELECT name, enabled, created_at FROM scopes WHERE id = :id
        """), {"id": scope_id}).fetchone()
        
        # Targets
        targets = conn.execute(text("""
            SELECT value, type FROM targets WHERE scope_id = :scope_id AND enabled = true
        """), {"scope_id": scope_id}).fetchall()
    
    return {
        "scope_id": scope_id,
        "scope_name": scope[0] if scope else None,
        "enabled": scope[1] if scope else None,
        "created_at": str(scope[2]) if scope else None,
        "targets": [{"value": t[0], "type": str(t[1])} for t in targets],
        "total_findings": sum(row[1] for row in findings_by_type),
        "findings_by_type": {row[0]: row[1] for row in findings_by_type},
        "unique_subdomains": subdomains,
        "recent_jobs": [
            {
                "id": j[0],
                "status": str(j[1]),
                "findings_count": j[2],
                "created_at": str(j[3]),
                "completed_at": str(j[4]) if j[4] else None
            }
            for j in jobs
        ]
    }


@app.get("/api/v1/scopes/{scope_id}/subdomains", tags=["Scope Findings"])
async def get_scope_subdomains(
    scope_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000)
):
    """Get all unique subdomains found for a scope"""
    offset = (page - 1) * page_size
    
    with get_connection() as conn:
        subdomains = conn.execute(text("""
            SELECT DISTINCT value, source, MIN(first_seen) as first_seen, MAX(last_seen) as last_seen
            FROM recon_findings 
            WHERE scope_id = :scope_id AND finding_type = 'subdomain'
            GROUP BY value, source
            ORDER BY value
            LIMIT :limit OFFSET :offset
        """), {"scope_id": scope_id, "limit": page_size, "offset": offset}).fetchall()
        
        total = conn.execute(text("""
            SELECT COUNT(DISTINCT value) FROM recon_findings 
            WHERE scope_id = :scope_id AND finding_type = 'subdomain'
        """), {"scope_id": scope_id}).scalar()
    
    return {
        "scope_id": scope_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "subdomains": [
            {
                "subdomain": s[0],
                "source": s[1],
                "first_seen": str(s[2]),
                "last_seen": str(s[3])
            }
            for s in subdomains
        ]
    }


@app.get("/api/v1/scopes/{scope_id}/dns", tags=["Scope Findings"])
async def get_scope_dns_records(
    scope_id: str,
    record_type: Optional[str] = None
):
    """Get all DNS records found for a scope"""
    with get_connection() as conn:
        where_clause = "WHERE scope_id = :scope_id AND finding_type LIKE 'dns_%'"
        params = {"scope_id": scope_id}
        
        if record_type:
            where_clause += " AND finding_type = :finding_type"
            params["finding_type"] = f"dns_{record_type.lower()}"
        
        records = conn.execute(text(f"""
            SELECT DISTINCT finding_type, value, extra_data::text, MIN(first_seen) as first_seen
            FROM recon_findings 
            {where_clause}
            GROUP BY finding_type, value, extra_data::text
            ORDER BY finding_type, value
        """), params).fetchall()
    
    return {
        "scope_id": scope_id,
        "total": len(records),
        "dns_records": [
            {
                "record_type": r[0].replace("dns_", "").upper(),
                "value": r[1],
                "extra_data": json.loads(r[2]) if r[2] else None,
                "first_seen": str(r[3])
            }
            for r in records
        ]
    }


# ==================== JOB FINDINGS ENDPOINTS ====================

@app.get("/api/v1/jobs/{job_id}/findings", tags=["Job Findings"])
async def get_job_findings(
    job_id: str,
    finding_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    """Get all findings from a specific job"""
    offset = (page - 1) * page_size
    
    with get_connection() as conn:
        where_clause = "WHERE job_id = :job_id"
        params = {"job_id": job_id, "limit": page_size, "offset": offset}
        
        if finding_type:
            where_clause += " AND finding_type = :finding_type"
            params["finding_type"] = finding_type
        
        findings = conn.execute(text(f"""
            SELECT id, finding_type, value, source, time, extra_data
            FROM recon_findings 
            {where_clause}
            ORDER BY time ASC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()
        
        total = conn.execute(text(f"""
            SELECT COUNT(*) FROM recon_findings {where_clause}
        """), params).scalar()
        
        # Get job info
        job = conn.execute(text("""
            SELECT scope_id, status, created_at, started_at, completed_at 
            FROM jobs WHERE id = :id
        """), {"id": job_id}).fetchone()
    
    return {
        "job_id": job_id,
        "scope_id": job[0] if job else None,
        "job_status": str(job[1]) if job else None,
        "job_created": str(job[2]) if job else None,
        "job_started": str(job[3]) if job else None,
        "job_completed": str(job[4]) if job else None,
        "total": total,
        "page": page,
        "page_size": page_size,
        "findings": [
            {
                "id": f[0],
                "finding_type": f[1],
                "value": f[2],
                "source": f[3],
                "discovered_at": str(f[4]),
                "extra_data": f[5]
            }
            for f in findings
        ]
    }


@app.get("/api/v1/jobs/{job_id}/summary", tags=["Job Findings"])
async def get_job_summary(job_id: str):
    """Get summary of findings from a specific job"""
    with get_connection() as conn:
        findings_by_type = conn.execute(text("""
            SELECT finding_type, COUNT(*) as count 
            FROM recon_findings 
            WHERE job_id = :job_id
            GROUP BY finding_type
        """), {"job_id": job_id}).fetchall()
        
        job = conn.execute(text("""
            SELECT j.scope_id, j.status, j.created_at, j.started_at, j.completed_at, 
                   j.triggered_by, s.name as scope_name
            FROM jobs j
            JOIN scopes s ON j.scope_id = s.id
            WHERE j.id = :id
        """), {"id": job_id}).fetchone()
    
    return {
        "job_id": job_id,
        "scope_id": job[0] if job else None,
        "scope_name": job[6] if job else None,
        "status": str(job[1]) if job else None,
        "triggered_by": job[5] if job else None,
        "created_at": str(job[2]) if job else None,
        "started_at": str(job[3]) if job else None,
        "completed_at": str(job[4]) if job else None,
        "total_findings": sum(row[1] for row in findings_by_type),
        "findings_by_type": {row[0]: row[1] for row in findings_by_type}
    }


# ==================== SEARCH ENDPOINTS ====================

@app.get("/api/v1/search", tags=["Search"])
async def search_findings(
    q: str = Query(..., min_length=2, description="Search query"),
    finding_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    """Search findings by value"""
    offset = (page - 1) * page_size
    
    with get_connection() as conn:
        where_clause = "WHERE value ILIKE :query"
        params = {"query": f"%{q}%", "limit": page_size, "offset": offset}
        
        if finding_type:
            where_clause += " AND finding_type = :finding_type"
            params["finding_type"] = finding_type
        
        if scope_id:
            where_clause += " AND scope_id = :scope_id"
            params["scope_id"] = scope_id
        
        findings = conn.execute(text(f"""
            SELECT rf.id, rf.finding_type, rf.value, rf.source, rf.time, rf.scope_id, 
                   rf.job_id, s.name as scope_name
            FROM recon_findings rf
            JOIN scopes s ON rf.scope_id = s.id
            {where_clause}
            ORDER BY rf.time DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()
        
        total = conn.execute(text(f"""
            SELECT COUNT(*) FROM recon_findings rf {where_clause}
        """), params).scalar()
    
    return {
        "query": q,
        "total": total,
        "page": page,
        "page_size": page_size,
        "findings": [
            {
                "id": f[0],
                "finding_type": f[1],
                "value": f[2],
                "source": f[3],
                "discovered_at": str(f[4]),
                "scope_id": f[5],
                "job_id": f[6],
                "scope_name": f[7]
            }
            for f in findings
        ]
    }


# ==================== CVE ENDPOINTS ====================

@app.get("/api/v1/scopes/{scope_id}/cves", tags=["CVE"])
async def get_cves_for_scope(
    scope_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    min_cvss: Optional[float] = Query(None, ge=0, le=10, description="Minimum CVSS score"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    """Get all CVE findings for a scope"""
    offset = (page - 1) * page_size
    
    with get_connection() as conn:
        where_clause = "WHERE rf.scope_id = :scope_id AND rf.finding_type = 'cve'"
        params = {"scope_id": scope_id, "limit": page_size, "offset": offset}
        
        if severity:
            where_clause += " AND rf.metadata->>'severity' = :severity"
            params["severity"] = severity.upper()
        
        if min_cvss is not None:
            where_clause += " AND (rf.metadata->>'cvss_score')::float >= :min_cvss"
            params["min_cvss"] = min_cvss
        
        findings = conn.execute(text(f"""
            SELECT rf.id, rf.value, rf.source, rf.time, rf.metadata, rf.job_id
            FROM recon_findings rf
            {where_clause}
            ORDER BY (rf.metadata->>'cvss_score')::float DESC NULLS LAST, rf.time DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()
        
        total = conn.execute(text(f"""
            SELECT COUNT(*) FROM recon_findings rf {where_clause}
        """), params).scalar()
        
        # Get severity summary
        severity_counts = conn.execute(text("""
            SELECT rf.metadata->>'severity' as severity, COUNT(*) as count
            FROM recon_findings rf
            WHERE rf.scope_id = :scope_id AND rf.finding_type = 'cve'
            GROUP BY rf.metadata->>'severity'
        """), {"scope_id": scope_id}).fetchall()
    
    return {
        "scope_id": scope_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "severity_summary": {row[0]: row[1] for row in severity_counts if row[0]},
        "cves": [
            {
                "id": f[0],
                "cve_id": f[1],
                "source": f[2],
                "discovered_at": str(f[3]),
                "job_id": f[5],
                **(f[4] if f[4] else {})
            }
            for f in findings
        ]
    }


@app.get("/api/v1/scopes/{scope_id}/cves/critical", tags=["CVE"])
async def get_critical_cves(
    scope_id: str,
    include_high: bool = Query(True, description="Include HIGH severity CVEs")
):
    """Get critical (and optionally high) severity CVEs for a scope"""
    with get_connection() as conn:
        severity_filter = "('CRITICAL')" if not include_high else "('CRITICAL', 'HIGH')"
        
        findings = conn.execute(text(f"""
            SELECT rf.id, rf.value, rf.source, rf.time, rf.metadata, rf.job_id
            FROM recon_findings rf
            WHERE rf.scope_id = :scope_id 
              AND rf.finding_type = 'cve'
              AND rf.metadata->>'severity' IN {severity_filter}
            ORDER BY (rf.metadata->>'cvss_score')::float DESC NULLS LAST, rf.time DESC
        """), {"scope_id": scope_id}).fetchall()
    
    return {
        "scope_id": scope_id,
        "total": len(findings),
        "cves": [
            {
                "id": f[0],
                "cve_id": f[1],
                "source": f[2],
                "discovered_at": str(f[3]),
                "job_id": f[5],
                **(f[4] if f[4] else {})
            }
            for f in findings
        ]
    }


@app.get("/api/v1/jobs/{job_id}/cves", tags=["CVE"])
async def get_cves_for_job(
    job_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity")
):
    """Get all CVE findings for a specific job"""
    with get_connection() as conn:
        where_clause = "WHERE rf.job_id = :job_id AND rf.finding_type = 'cve'"
        params = {"job_id": job_id}
        
        if severity:
            where_clause += " AND rf.metadata->>'severity' = :severity"
            params["severity"] = severity.upper()
        
        findings = conn.execute(text(f"""
            SELECT rf.id, rf.value, rf.source, rf.time, rf.metadata
            FROM recon_findings rf
            {where_clause}
            ORDER BY (rf.metadata->>'cvss_score')::float DESC NULLS LAST
        """), params).fetchall()
        
        # Get related port scan findings for context
        ports = conn.execute(text("""
            SELECT rf.value, rf.metadata
            FROM recon_findings rf
            WHERE rf.job_id = :job_id AND rf.finding_type = 'port'
            ORDER BY rf.value
        """), {"job_id": job_id}).fetchall()
    
    return {
        "job_id": job_id,
        "total_cves": len(findings),
        "total_ports_scanned": len(ports),
        "cves": [
            {
                "id": f[0],
                "cve_id": f[1],
                "source": f[2],
                "discovered_at": str(f[3]),
                **(f[4] if f[4] else {})
            }
            for f in findings
        ],
        "scanned_ports": [
            {
                "port": p[0],
                **(p[1] if p[1] else {})
            }
            for p in ports
        ]
    }


# ==================== PORT/SERVICE ENDPOINTS ====================

@app.get("/api/v1/scopes/{scope_id}/ports", tags=["Ports"])
async def get_ports_for_scope(
    scope_id: str,
    state: Optional[str] = Query("open", description="Port state filter (open, closed, filtered)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000)
):
    """Get all port findings for a scope"""
    offset = (page - 1) * page_size
    
    with get_connection() as conn:
        where_clause = "WHERE rf.scope_id = :scope_id AND rf.finding_type = 'port'"
        params = {"scope_id": scope_id, "limit": page_size, "offset": offset}
        
        if state:
            where_clause += " AND rf.metadata->>'state' = :state"
            params["state"] = state
        
        findings = conn.execute(text(f"""
            SELECT rf.id, rf.value, rf.source, rf.time, rf.metadata, rf.job_id
            FROM recon_findings rf
            {where_clause}
            ORDER BY (rf.value)::int ASC, rf.time DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()
        
        total = conn.execute(text(f"""
            SELECT COUNT(*) FROM recon_findings rf {where_clause}
        """), params).scalar()
        
        # Get unique services
        services = conn.execute(text("""
            SELECT DISTINCT rf.metadata->>'service' as service, COUNT(*) as count
            FROM recon_findings rf
            WHERE rf.scope_id = :scope_id AND rf.finding_type = 'port'
            GROUP BY rf.metadata->>'service'
            ORDER BY count DESC
        """), {"scope_id": scope_id}).fetchall()
    
    return {
        "scope_id": scope_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "services_summary": {row[0]: row[1] for row in services if row[0]},
        "ports": [
            {
                "id": f[0],
                "port": f[1],
                "source": f[2],
                "discovered_at": str(f[3]),
                "job_id": f[5],
                **(f[4] if f[4] else {})
            }
            for f in findings
        ]
    }


@app.get("/api/v1/scopes/{scope_id}/services", tags=["Ports"])
async def get_services_for_scope(
    scope_id: str,
    service_name: Optional[str] = Query(None, description="Filter by service name")
):
    """Get all services with versions discovered for a scope"""
    with get_connection() as conn:
        where_clause = "WHERE rf.scope_id = :scope_id AND rf.finding_type = 'port'"
        params = {"scope_id": scope_id}
        
        if service_name:
            where_clause += " AND rf.metadata->>'service' ILIKE :service_name"
            params["service_name"] = f"%{service_name}%"
        
        findings = conn.execute(text(f"""
            SELECT rf.value as port, rf.metadata->>'service' as service,
                   rf.metadata->>'product' as product, rf.metadata->>'version' as version,
                   rf.metadata->>'host' as host, rf.time, rf.id
            FROM recon_findings rf
            {where_clause}
            ORDER BY rf.metadata->>'service', (rf.value)::int
        """), params).fetchall()
        
        # Group by service
        services = {}
        for f in findings:
            service = f[1] or 'unknown'
            if service not in services:
                services[service] = []
            services[service].append({
                "id": f[6],
                "port": f[0],
                "product": f[2],
                "version": f[3],
                "host": f[4],
                "discovered_at": str(f[5])
            })
    
    return {
        "scope_id": scope_id,
        "total_services": len(services),
        "total_ports": len(findings),
        "services": services
    }


@app.get("/api/v1/scopes/{scope_id}/vulnerable-services", tags=["Ports"])
async def get_vulnerable_services(
    scope_id: str,
    min_severity: Optional[str] = Query("MEDIUM", description="Minimum CVE severity")
):
    """Get services that have associated CVEs"""
    severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
    min_level = severity_order.get(min_severity.upper(), 2) if min_severity else 0
    
    with get_connection() as conn:
        # Get CVEs with their associated service info
        cves = conn.execute(text("""
            SELECT rf.value as cve_id, rf.metadata->>'severity' as severity,
                   rf.metadata->>'cvss_score' as cvss, rf.metadata->>'service' as service,
                   rf.metadata->>'product' as product, rf.metadata->>'version' as version,
                   rf.metadata->>'host' as host, rf.metadata->>'port' as port
            FROM recon_findings rf
            WHERE rf.scope_id = :scope_id AND rf.finding_type = 'cve'
            ORDER BY (rf.metadata->>'cvss_score')::float DESC NULLS LAST
        """), {"scope_id": scope_id}).fetchall()
    
    # Filter by severity and group by service
    vulnerable_services = {}
    for cve in cves:
        sev = cve[1] or 'UNKNOWN'
        if severity_order.get(sev, 0) >= min_level:
            service_key = f"{cve[4] or cve[3]}:{cve[5]}" if cve[5] else (cve[4] or cve[3] or 'unknown')
            if service_key not in vulnerable_services:
                vulnerable_services[service_key] = {
                    "service": cve[3],
                    "product": cve[4],
                    "version": cve[5],
                    "hosts": set(),
                    "cves": []
                }
            if cve[6]:
                vulnerable_services[service_key]["hosts"].add(f"{cve[6]}:{cve[7]}")
            vulnerable_services[service_key]["cves"].append({
                "cve_id": cve[0],
                "severity": sev,
                "cvss_score": float(cve[2]) if cve[2] else None
            })
    
    # Convert sets to lists for JSON serialization
    for svc in vulnerable_services.values():
        svc["hosts"] = list(svc["hosts"])
    
    return {
        "scope_id": scope_id,
        "min_severity": min_severity,
        "total_vulnerable_services": len(vulnerable_services),
        "vulnerable_services": vulnerable_services
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)



