"""
Recon Manager - Data Models
All models follow the enable/disable principle
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TargetType(str, Enum):
    """Types of recon targets"""
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    CIDR_RANGE = "cidr_range"
    ASN = "asn"
    TLS_CERT = "tls_cert"


class ReconMode(str, Enum):
    """Recon operation modes"""
    PASSIVE = "passive"
    ACTIVE = "active"


class JobStatus(str, Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class AggressivenessProfile(str, Enum):
    """Scan aggressiveness levels"""
    STEALTH = "stealth"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"


# ==================== TARGET MODELS ====================

class Target(BaseModel):
    """Recon target within a scope"""
    id: Optional[str] = None
    scope_id: str
    type: TargetType
    value: str  # Domain, IP, CIDR, ASN, etc.
    enabled: bool = True
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TargetCreate(BaseModel):
    """Create new target"""
    scope_id: Optional[str] = None  # Set by API from path parameter
    type: TargetType
    value: str
    enabled: bool = True
    description: Optional[str] = None


class TargetUpdate(BaseModel):
    """Update target"""
    value: Optional[str] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


# ==================== PASSIVE RECON FEATURES ====================

class PassiveFeatures(BaseModel):
    """Enable/disable individual passive recon features"""
    certificate_transparency: bool = True
    dns_history: bool = True
    asn_expansion: bool = False  # Disabled by default
    osint_apis: bool = True
    search_engine_scraping: bool = False  # Disabled by default
    
    # Individual OSINT sources
    crtsh: bool = True
    hackertarget: bool = True
    threatcrowd: bool = True
    virustotal: bool = True
    dnsdumpster: bool = False
    rapiddns: bool = True
    wayback_machine: bool = True
    anubisdb: bool = True
    urlscan: bool = True
    github_search: bool = False  # Requires API key
    commoncrawl: bool = True
    censys: bool = False  # Requires API key


# ==================== ACTIVE RECON FEATURES ====================

class ActiveFeatures(BaseModel):
    """Enable/disable individual active recon features"""
    subdomain_enumeration: bool = True
    subdirectory_discovery: bool = False
    port_scanning: bool = True  # Enable Nmap scanning
    vhost_enumeration: bool = False
    http_probing: bool = True
    cve_lookup: bool = True  # Enable CVE lookup after port scanning
    
    # Subdomain-specific
    dns_bruteforce: bool = False
    permutation_scanning: bool = False
    
    # HTTP-specific
    technology_detection: bool = True
    screenshot_capture: bool = False


# ==================== NMAP CONFIGURATION ====================

class NmapScanType(str, Enum):
    """Nmap scan types"""
    FAST = "fast"
    DEFAULT = "default"
    FULL = "full"


class NmapConfig(BaseModel):
    """Nmap scanning configuration"""
    enabled: bool = True
    scan_type: NmapScanType = NmapScanType.DEFAULT
    ports: Optional[str] = None  # e.g., "22,80,443" or "1-1000"
    threads: int = Field(5, ge=1, le=20, description="Number of parallel scan threads")
    timeout: int = Field(300, ge=60, le=3600, description="Timeout per host in seconds")
    check_cves: bool = True  # Enable CVE lookup after scanning


class CVEConfig(BaseModel):
    """CVE/NVD lookup configuration"""
    enabled: bool = True
    nvd_api_key: Optional[str] = None  # NVD API key for higher rate limits
    max_results_per_service: int = Field(20, ge=1, le=100)
    severity_threshold: Optional[str] = None  # "LOW", "MEDIUM", "HIGH", "CRITICAL"


# ==================== RECON PARAMETERS ====================

class ReconParameters(BaseModel):
    """Configurable parameters for recon jobs"""
    # Global settings
    aggressiveness: AggressivenessProfile = AggressivenessProfile.NORMAL
    global_timeout: int = Field(3600, description="Global timeout in seconds")
    per_request_timeout: int = Field(30, description="Per-request timeout")
    
    # Rate limiting
    rate_limit_enabled: bool = True
    requests_per_second: int = Field(10, description="Max requests per second")
    max_concurrent: int = Field(10, description="Max concurrent requests")
    retry_count: int = Field(3, description="Number of retries on failure")
    
    # HTTP settings
    http_method: str = Field("GET", description="Default HTTP method")
    custom_headers: Optional[Dict[str, str]] = None
    user_agent: Optional[str] = "ReconManager/1.0"
    follow_redirects: bool = True
    
    # Depth controls
    subdomain_depth: int = Field(3, description="Max subdomain recursion depth")
    subdirectory_depth: int = Field(3, description="Max subdirectory depth")
    
    # Wordlists
    subdomain_wordlist: Optional[str] = None
    subdirectory_wordlist: Optional[str] = None


# ==================== SCHEDULE MODEL ====================

class Schedule(BaseModel):
    """Recon job schedule"""
    id: Optional[str] = None
    scope_id: str
    name: str
    enabled: bool = True
    mode: ReconMode
    cron_expression: str  # e.g., "0 */6 * * *"
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


class ScheduleCreate(BaseModel):
    """Create new schedule"""
    scope_id: Optional[str] = None  # Optional, set from URL path
    name: str
    mode: ReconMode
    cron_expression: str
    enabled: bool = True
    description: Optional[str] = None


class ScheduleUpdate(BaseModel):
    """Update schedule"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    description: Optional[str] = None


# ==================== DATA SOURCE MODELS ====================

class DataSource(BaseModel):
    """External data source configuration"""
    id: Optional[str] = None
    name: str
    enabled: bool = True
    source_type: str  # "osint", "api", "passive", "active"
    requires_api_key: bool = False
    global_enabled: bool = True  # Global on/off
    scope_overrides: Optional[Dict[str, bool]] = None  # Per-scope enable/disable
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class APIKey(BaseModel):
    """API key for external sources"""
    id: Optional[str] = None
    source_name: str  # "shodan", "censys", "virustotal", etc.
    key_value: str  # Encrypted in storage
    enabled: bool = True
    scope_id: Optional[str] = None  # None = global, otherwise scope-specific
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class APIKeyCreate(BaseModel):
    """Create API key"""
    source_name: str
    key_value: str
    enabled: bool = True
    scope_id: Optional[str] = None


class APIKeyUpdate(BaseModel):
    """Update API key"""
    key_value: Optional[str] = None
    enabled: Optional[bool] = None


# ==================== SCOPE MODEL ====================

class ScopeConfig(BaseModel):
    """Recon configuration per scope"""
    passive_enabled: bool = True
    active_enabled: bool = False
    
    passive_features: PassiveFeatures = PassiveFeatures()
    active_features: ActiveFeatures = ActiveFeatures()
    parameters: ReconParameters = ReconParameters()
    
    # Nmap and CVE configuration
    nmap: NmapConfig = NmapConfig()
    cve: CVEConfig = CVEConfig()


class Scope(BaseModel):
    """Scope - Primary isolation boundary"""
    id: Optional[str] = None
    name: str  # e.g., "google.com", "meta.com"
    enabled: bool = True
    description: Optional[str] = None
    
    # Targets belong to scope
    targets: List[Target] = []
    
    # Configuration
    config: ScopeConfig = ScopeConfig()
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


class ScopeCreate(BaseModel):
    """Create new scope"""
    name: str
    enabled: bool = True
    description: Optional[str] = None
    config: Optional[ScopeConfig] = ScopeConfig()


class ScopeUpdate(BaseModel):
    """Update scope"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None
    config: Optional[ScopeConfig] = None


# ==================== JOB MODELS ====================

class Job(BaseModel):
    """Recon job"""
    id: Optional[str] = None
    scope_id: str
    mode: ReconMode
    status: JobStatus = JobStatus.PENDING
    enabled: bool = True
    
    # Job details
    triggered_by: str  # "schedule", "manual", "api"
    schedule_id: Optional[str] = None
    
    # Execution
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Results metadata (not actual results)
    targets_scanned: int = 0
    findings_count: int = 0
    errors_count: int = 0
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class JobCreate(BaseModel):
    """Create/trigger new job"""
    scope_id: str
    mode: ReconMode
    triggered_by: str = "manual"
    schedule_id: Optional[str] = None


class JobUpdate(BaseModel):
    """Update job"""
    status: Optional[JobStatus] = None
    enabled: Optional[bool] = None


# ==================== RESPONSE MODELS ====================

class PaginatedResponse(BaseModel):
    """Paginated API response"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class APIResponse(BaseModel):
    """Standard API response"""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
