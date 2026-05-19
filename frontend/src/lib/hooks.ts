'use client';

import useSWR, { SWRConfiguration } from 'swr';
import { fetcher } from './api';

/* ── Typed shapes for paginated and bare list responses ───────────────────── */

export interface Paginated<T> { items: T[]; total: number; }

export interface Article {
  id: string;
  title: string;
  url: string;
  source_name: string;
  author: string | null;
  published_at: string | null;
  fetched_at: string;
  summary: string | null;
  tags: string[];
  confidence_score: number | null;
  analyst_status: string;
}

export interface CVE {
  cve_id: string;
  published_at: string | null;
  last_modified_at: string | null;
  description: string | null;
  cvss_v3_score: number | null;
  cvss_v3_vector: string | null;
  severity: string | null;
  cwe: string[];
  affected_products: Record<string, unknown>;
  references: string[];
  analyst_status: string;
}

export interface CVEDetail extends CVE {
  epss: number | null;
  epss_percentile: number | null;
  kev: boolean;
  kev_date_added: string | null;
  kev_ransomware_use: boolean;
}

export interface Indicator {
  id: string;
  type: string;
  normalized_value: string;
  raw_value: string;
  first_seen: string;
  last_seen: string;
  tags: string[];
  confidence_score: number;
  analyst_status: string;
}

export interface Actor {
  id: string;
  mitre_id: string | null;
  name: string;
  aliases: string[];
  origin_country: string | null;
  description: string | null;
  motivation: string[];
  active_since: string | null;
  last_seen: string | null;
  target_sectors: string[];
  target_countries: string[];
  status: string;
  analyst_status: string;
}

export interface RansomwareGroup {
  id: string;
  name: string;
  aliases: string[];
  status: string;
  first_seen: string | null;
  last_seen: string | null;
  variants: string[];
  leak_site_url: string | null;
  ransom_range: Record<string, unknown>;
  description?: string | null;
  profile_url?: string | null;
  tor_urls?: string[];
  domains?: string[];
  locations?: string[];
  iocs?: Record<string, unknown>;
  victim_count?: number;
  target_countries?: string[];
  target_sectors?: string[];
  actor_id?: string | null;
}

export interface RansomwareVictim {
  id: string;
  group_id: string;
  group_name?: string | null;
  actor_id?: string | null;
  actor_name?: string | null;
  victim_name: string;
  sector: string | null;
  country: string | null;
  disclosed_at: string | null;
  source: string;
}

export interface Threat {
  id: string;
  type: string;
  title: string;
  source: string;
  source_url: string | null;
  observed_at: string | null;
  summary: string | null;
  severity: string | null;
  details: Record<string, unknown>;
  confidence_score: number;
  analyst_status: string;
}

export interface Asset {
  id: string;
  hostname: string;
  ip: string | null;
  os: string | null;
  software: Record<string, unknown>;
  device_type: string | null;
  criticality: string | null;
  owner: string | null;
  location: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  username: string;
  role: string;
  role_id?: string;
  permissions?: string[];
  supplementary_permissions?: string[];
  email: string | null;
  active: boolean;
  created_at?: string;
  last_login_at: string | null;
}

export interface Role {
  id: string;
  name: string;
  permissions: string[];
  user_count?: number;
}

export interface SessionRow {
  id: string;
  user_id: string;
  username?: string;
  user_agent: string | null;
  ip: string | null;
  issued_at: string;
  expires_at: string;
  revoked: boolean;
}

export interface JobInfo {
  id: string;
  name?: string;
  next_run_time: string | null;
  trigger?: string;
  schedule?: string;
}

export interface RunInfo {
  run_id: string;
  job_id: string;
  triggered_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  status: string;
  http_status: number | null;
  error_detail: string | null;
}

export interface Report {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  model_name: string;
  prompt_version: string;
  generated_at: string;
}

export interface Policy {
  id: string;
  scope: string;
  category: string | null;
  resource_type: string;
  resource_id: string | null;
  mode: string;
  actions: string[];
  cmdb_filter: boolean;
  priority: number;
  active: boolean;
}

export interface ProfileIdentity {
  name: string;
  sector: string;
  sub_sector?: string;
  employee_count_range?: string;
  hq_country: string;
  countries_of_operation: string[];
  public_domains: string[];
  public_ip_ranges: string[];
  asn_numbers: string[];
  language: string;
}
export interface ProfileTechnology {
  operating_systems: string[];
  endpoint_os: string[];
  software: string[];
  network_devices: string[];
  cloud_providers: string[];
  identity_providers: string[];
  remote_access: string[];
  security_tools: string[];
  industrial_ot: boolean;
}
export interface ProfileExposure {
  internet_facing_services: string[];
  mobile_workforce: boolean;
  third_party_access: boolean;
  supply_chain_vendors: string[];
  critical_data_types: string[];
}
export interface ProfileCompliance {
  regulatory_frameworks: string[];
  certifications: string[];
  data_residency_requirements: string[];
}
export interface ProfileGeopolitical {
  geopolitical_regions: string[];
  conflict_adjacent: boolean;
  notable_partnerships: string[];
  sanctions_exposure: boolean;
}
export interface ProfileRisk {
  risk_appetite: string;
  crown_jewels: string[];
  previous_incidents: string[];
  threat_concerns: string[];
}
export interface Profile {
  version: number;
  edited_by: string;
  edited_at: string;
  identity: ProfileIdentity;
  technology: ProfileTechnology;
  exposure: ProfileExposure;
  compliance: ProfileCompliance;
  geopolitical: ProfileGeopolitical;
  risk: ProfileRisk;
}

/* ── Generic SWR helpers ──────────────────────────────────────────────────── */

const DEFAULTS: SWRConfiguration = {
  revalidateOnFocus: false,
  dedupingInterval: 5_000,
  errorRetryCount: 1,
};

function key(path: string, params?: Record<string, string | number | boolean | undefined>) {
  if (!params) return path;
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return qs ? `${path}?${qs}` : path;
}

export function useList<T>(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const { data, error, isLoading, mutate } = useSWR<Paginated<T> | T[]>(
    key(path, params), fetcher, DEFAULTS,
  );
  // Normalise to {items, total}
  const items = Array.isArray(data) ? data : data?.items ?? [];
  const total = Array.isArray(data) ? data.length : data?.total ?? 0;
  return { items: items as T[], total, isLoading, error, mutate };
}

export function useOne<T>(path: string | null) {
  const { data, error, isLoading, mutate } = useSWR<T>(
    path, fetcher, DEFAULTS,
  );
  return { data, isLoading, error, mutate };
}

/* ── Convenience hooks for each entity ────────────────────────────────────── */

export const useArticles  = (params?: Record<string, string | number | boolean | undefined>) => useList<Article>('/articles', params);
export const useArticle   = (id?: string) => useOne<Article>(id ? `/articles/${id}` : null);

export const useCVEs      = (params?: Record<string, string | number | boolean | undefined>) => useList<CVE>('/cves', params);
export const useCVE       = (id?: string) => useOne<CVEDetail>(id ? `/cves/${id}` : null);

export const useIndicators= (params?: Record<string, string | number | boolean | undefined>) => useList<Indicator>('/indicators', params);
export const useIndicator = (id?: string) => useOne<Indicator>(id ? `/indicators/${id}` : null);

export const useActors    = (params?: Record<string, string | number | boolean | undefined>) => useList<Actor>('/actors', params);
export const useActor     = (id?: string) => useOne<Actor>(id ? `/actors/${id}` : null);

export const useRansomwareGroups  = (params?: Record<string, string | number | boolean | undefined>) => useList<RansomwareGroup>('/ransomware/groups', params);
export const useRansomwareVictims = (params?: Record<string, string | number | boolean | undefined>) => useList<RansomwareVictim>('/ransomware/victims', params);

export const useThreats   = (params?: Record<string, string | number | boolean | undefined>) => useList<Threat>('/threats', params);
export const useThreat    = (id?: string) => useOne<Threat>(id ? `/threats/${id}` : null);
export const useAssets    = (params?: Record<string, string | number | boolean | undefined>) => useList<Asset>('/assets', params);

export const useUsers     = () => useList<User>('/users');
export const useRoles     = () => useList<Role>('/roles');
export const useSessions  = () => useList<SessionRow>('/sessions');

export const useJobs      = () => useList<JobInfo>('/jobs');
export const useRuns      = (params?: Record<string, string | number | boolean | undefined>) => useList<RunInfo>('/runs', params);

export const useReports   = (params?: Record<string, string | number | boolean | undefined>) => useList<Report>('/reports', params);
export const usePolicies  = () => useList<Policy>('/policies');

export const useProfile   = () => useOne<Profile>('/profile/latest');

/* Dashboard aggregation — one BFF call that fans out */
export interface DashboardData {
  iocs_total: number;
  cves_total: number;
  threats_total: number;
  articles_total: number;
  actors_total: number;
  services_healthy: number;
  services_total: number;
  top_cves: { cve_id: string; severity: string; cvss_v3_score: number | null; relevance: number; kev: boolean; description: string | null }[];
  top_actors: { id: string; name: string; origin_country: string | null; likelihood: number; target_sectors: string[]; motivation: string[] }[];
  recent_runs: RunInfo[];
  latest_brief: Report | null;
  // Latest geo_prediction report (orchestrator /analyze/geo cycle).
  // Payload: { outlook, summary, emerging_threats, affected_sectors,
  //            recommended_monitoring }.
  latest_geo: Report | null;
}

export const useDashboard = () => useOne<DashboardData>('/dashboard');
