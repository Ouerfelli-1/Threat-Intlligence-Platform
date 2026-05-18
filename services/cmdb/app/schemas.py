import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssetBase(BaseModel):
    hostname: str
    ip: str | None = None
    os: str | None = None
    software: dict[str, Any] = Field(default_factory=dict)
    device_type: str | None = None
    criticality: str | None = None
    owner: str | None = None
    location: str | None = None
    tags: list[str] = Field(default_factory=list)


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    hostname: str | None = None
    ip: str | None = None
    os: str | None = None
    software: dict[str, Any] | None = None
    device_type: str | None = None
    criticality: str | None = None
    owner: str | None = None
    location: str | None = None
    tags: list[str] | None = None


class AssetOut(AssetBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AssetList(BaseModel):
    items: list[AssetOut]
    total: int


# ---- Company profile ----


class Identity(BaseModel):
    name: str
    sector: str
    sub_sector: str | None = None
    employee_count_range: str | None = None
    hq_country: str
    countries_of_operation: list[str] = Field(default_factory=list)
    public_domains: list[str] = Field(default_factory=list)
    public_ip_ranges: list[str] = Field(default_factory=list)
    asn_numbers: list[str] = Field(default_factory=list)
    language: str = "en"


class Technology(BaseModel):
    operating_systems: list[str] = Field(default_factory=list)
    endpoint_os: list[str] = Field(default_factory=list)
    software: list[str] = Field(default_factory=list)
    network_devices: list[str] = Field(default_factory=list)
    cloud_providers: list[str] = Field(default_factory=list)
    identity_providers: list[str] = Field(default_factory=list)
    remote_access: list[str] = Field(default_factory=list)
    security_tools: list[str] = Field(default_factory=list)
    industrial_ot: bool = False


class Exposure(BaseModel):
    internet_facing_services: list[str] = Field(default_factory=list)
    mobile_workforce: bool = False
    third_party_access: bool = False
    supply_chain_vendors: list[str] = Field(default_factory=list)
    critical_data_types: list[str] = Field(default_factory=list)


class Compliance(BaseModel):
    regulatory_frameworks: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    data_residency_requirements: list[str] = Field(default_factory=list)


class Geopolitical(BaseModel):
    geopolitical_regions: list[str] = Field(default_factory=list)
    conflict_adjacent: bool = False
    notable_partnerships: list[str] = Field(default_factory=list)
    sanctions_exposure: bool = False


class Risk(BaseModel):
    risk_appetite: str = "medium"
    crown_jewels: list[str] = Field(default_factory=list)
    previous_incidents: list[str] = Field(default_factory=list)
    threat_concerns: list[str] = Field(default_factory=list)


class CompanyProfile(BaseModel):
    identity: Identity
    technology: Technology = Field(default_factory=Technology)
    exposure: Exposure = Field(default_factory=Exposure)
    compliance: Compliance = Field(default_factory=Compliance)
    geopolitical: Geopolitical = Field(default_factory=Geopolitical)
    risk: Risk = Field(default_factory=Risk)


class CompanyProfileOut(CompanyProfile):
    version: int
    edited_by: str | None
    edited_at: datetime


class CompanyProfilePatch(BaseModel):
    identity: Identity | None = None
    technology: Technology | None = None
    exposure: Exposure | None = None
    compliance: Compliance | None = None
    geopolitical: Geopolitical | None = None
    risk: Risk | None = None


class AutoAddRequest(BaseModel):
    source_resource_type: str
    source_resource_id: str
    product_name: str | None = None
    actor: str | None = None


class ProfileChangeLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    change_type: str
    source_resource_type: str | None
    source_resource_id: str | None
    added_value: str | None
    added_by_analyst: str | None
    recorded_at: datetime


# ---- Tag catalog ----

# Resource types that can carry tags. Frontend tag-picker filters by these.
TAG_SCOPES = {"ioc", "asset", "feed", "actor", "threat", "article", "cve"}


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    color: str | None = Field(None, max_length=16, description="Hex like #58a6ff")
    scopes: list[str] = Field(default_factory=list, description="Subset of: ioc, asset, feed, actor, threat, article, cve")


class TagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = None
    color: str | None = Field(None, max_length=16)
    scopes: list[str] | None = None


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    color: str | None
    scopes: list[str]
    created_at: datetime
    updated_at: datetime
    created_by: str | None
