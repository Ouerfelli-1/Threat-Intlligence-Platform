export interface ExternalReference {
  source_name: string;
  description?: string;
  url?: string;
}

export interface Tool {
  id: string;
  type: 'tool';
  spec_version: '2.1';
  name: string;
  description?: string;
  tool_types: string[];
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
}

export interface AttackAction {
  id: string;
  type: 'action' | 'attack-action'; // Support both formats
  spec_version: '2.1';
  name: string;
  description: string;
  technique_id?: string;
  tactic_id?: string;
  tactic_name?: string;
  technique_ref?: string;
  tactic_ref?: string;
  command_ref?: string;
  external_references?: ExternalReference[];
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
  // Action properties
  targeted_assets?: string[];
  asset_impact_level?: 'low' | 'medium' | 'high';
}

export interface AttackAsset {
  id: string;
  type: 'attack-asset';
  spec_version: '2.1';
  name: string;
  description: string;
  role?: string;
  impact?: string;
  details?: {
    os?: string;
    services?: string[];
  };
  // Asset properties
  affected_by?: string[];
  risk_level?: 'low' | 'medium' | 'high' | 'very-high';
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
  // Atomic indicator properties (when asset represents IOCs)
  indicator_type?: 'ip-address' | 'domain' | 'file-hash' | 'url' | 'user-account' | 'registry-key' | 'network-port';
  indicator_value?: string;
  indicator_reputation?: 'malicious' | 'suspicious' | 'clean' | 'unknown';
  // Specific indicator details
  ip_type?: 'ipv4' | 'ipv6';
  domain_type?: 'fqdn' | 'subdomain' | 'tld';
  hash_type?: 'md5' | 'sha1' | 'sha256' | 'sha512';
  username?: string;
  account_domain?: string;
  account_type?: 'admin' | 'user' | 'service' | 'system';
  compromised?: boolean;
  registry_hive?: 'HKLM' | 'HKCU' | 'HKCR' | 'HKU' | 'HKCC';
  registry_key_path?: string;
  registry_value_name?: string;
  registry_value_data?: string;
  port_number?: number;
  port_protocol?: 'tcp' | 'udp' | 'icmp';
  port_service?: string;
  port_state?: 'open' | 'closed' | 'filtered';
}

export interface AttackCondition {
  id: string;
  type: 'attack-condition';
  spec_version: '2.1';
  name: string;
  description: string;
  pattern?: string;
  pattern_type?: string;
  operator?: 'AND' | 'OR';
  context?: string;
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
}

export interface AttackOperator {
  id: string;
  type: 'attack-operator';
  spec_version: '2.1';
  name: string;
  operator: 'AND' | 'OR';
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
}

export interface Infrastructure {
  id: string;
  type: 'infrastructure';
  spec_version: '2.1';
  name: string;
  description: string;
  infrastructure_types: string[];
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
}

export interface Vulnerability {
  id: string;
  type: 'vulnerability';
  spec_version: '2.1';
  name: string;
  description: string;
  cve_id?: string;
  cvss_score?: number;
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
}

export interface Process {
  id: string;
  type: 'process';
  spec_version: '2.1';
  name: string;
  description: string;
  process_type?: string;
  pid?: number;
  parent_process?: string;
  command_line?: string;
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
}

export interface FileNode {
  id: string;
  type: 'file';
  spec_version: '2.1';
  name: string;
  description: string;
  file_type?: string;
  path?: string;
  hash?: string;
  size?: number;
  source_excerpt?: string;
  confidence?: 'low' | 'medium' | 'high';
}


export interface AttackFlow {
  id: string;
  type: 'attack-flow';
  spec_version: '2.1';
  scope: 'incident' | 'campaign' | 'threat-actor' | 'malware' | 'attack-tree' | 'other';
  start_refs: string[];
  name?: string;
  description?: string;
}

export type AttackFlowNode = AttackAction | AttackAsset | AttackCondition | AttackOperator | Tool | Infrastructure | Vulnerability | Process | FileNode;

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  label: string;
} 