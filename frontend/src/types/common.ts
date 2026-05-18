export type AnalystStatus = 'unreviewed' | 'relevant' | 'not_relevant' | 'escalated' | 'reviewed';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

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
  confidence_score: number;
  confidence_inputs: Record<string, unknown>;
  analyst_status: AnalystStatus;
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
  affected_products: unknown;
  references: string[];
  analyst_status: AnalystStatus;
}

export interface CVEDetail extends CVE {
  epss: number | null;
  epss_percentile: number | null;
  kev: boolean;
  kev_date_added: string | null;
  kev_ransomware_use: boolean | null;
}

export interface Threat {
  id: string;
  type: string;
  title: string;
  source: string;
  source_url: string | null;
  observed_at: string;
  summary: string | null;
  severity: string | null;
  confidence_score: number;
  analyst_status: AnalystStatus;
}

export interface IOC {
  id: string;
  type: string;
  normalized_value: string;
  raw_value: string;
  first_seen: string;
  last_seen: string;
  tags: string[];
  confidence_score: number;
  analyst_status: AnalystStatus;
}

export interface IOCWithSources extends IOC {
  sources: Array<{
    source_name: string;
    source_id: string | null;
    first_reported_at: string;
    last_reported_at: string;
    malware_family: string | null;
    threat_type: string | null;
  }>;
}

export interface Actor {
  id: string;
  mitre_id: string | null;
  name: string;
  aliases: string[];
  origin_country: string | null;
  motivation: string[];
  active_since: string | null;
  last_seen: string | null;
  target_sectors: string[];
  target_countries: string[];
  status: string | null;
  analyst_status: AnalystStatus;
}

export interface ActorDetail extends Actor {
  ttps: Array<{
    technique_id: string;
    technique_name: string;
    confidence: number;
  }>;
  tools: Array<{
    id: string;
    name: string;
    type: string;
    mitre_id: string | null;
  }>;
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
  ransom_range: Record<string, unknown> | null;
}

export interface RansomwareVictim {
  id: string;
  group_id: string;
  victim_name: string;
  sector: string | null;
  country: string | null;
  disclosed_at: string | null;
  source: string | null;
}

export interface Insight {
  payload: Record<string, unknown> | null;
  model_name: string | null;
  prompt_version: string | null;
  generated_at: string | null;
  analyst_override: Record<string, unknown> | null;
}

export interface Note {
  id: string;
  body: string;
  pinned: boolean;
  author: string;
  created_at: string;
  updated_at: string;
}

export interface SchedulerJob {
  id: string;
  name: string | null;
  next_run_time: string | null;
  trigger: string | null;
}

export interface SchedulerRun {
  run_id: string;
  job_id: string;
  triggered_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  status: string;
  http_status: number | null;
  error_detail: string | null;
}

export interface Investigation {
  id: string;
  indicator_type: string;
  normalized_value: string;
  raw_value: string;
  status: string;
  verdict: string | null;
  confidence: number | null;
  risk_score: number | null;
  summary: string | null;
  payload: Record<string, unknown> | null;
  model_name: string | null;
  investigated_at: string;
  duration_ms: number | null;
}

export interface CompanyProfile {
  version: number;
  edited_by: string | null;
  edited_at: string;
  identity: {
    name: string;
    sector: string;
    hq_country: string;
    public_domains: string[];
    public_ip_ranges: string[];
    asn_numbers: string[];
    [key: string]: unknown;
  };
  technology: {
    software: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
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

export interface WazuhAlert {
  alert_id: string;
  agent_id: string | null;
  agent_name: string | null;
  rule_id: string | null;
  rule_description: string | null;
  severity: number;
  timestamp: string;
}

export interface Policy {
  id: string;
  scope: string;
  category: string | null;
  resource_type: string | null;
  resource_id: string | null;
  mode: string;
  actions: string[];
  cmdb_filter: boolean;
  priority: number;
  active: boolean;
}
