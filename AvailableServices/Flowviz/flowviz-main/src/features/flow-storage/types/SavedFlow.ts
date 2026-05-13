import { Node, Edge, Viewport } from 'reactflow';

export interface SavedFlow {
  id: string;
  title: string;
  sourceUrl?: string;
  sourceText?: string;
  inputMode: 'url' | 'text';
  
  // Flow data
  nodes: Node[];
  edges: Edge[];
  
  // Metadata
  metadata: {
    createdAt: string;
    updatedAt: string;
    version: string;
    description?: string;
    tags: string[];
    nodeCount: number;
    edgeCount: number;
  };
  
  // Visualization state
  visualization: {
    viewport?: Viewport;
    storyMode?: {
      enabled: boolean;
      currentStep?: number;
    };
  };
  
  // Analysis metadata
  analysis: {
    duration?: number; // How long analysis took (ms)
    confidence?: 'low' | 'medium' | 'high';
    extractedTechniques?: string[];
    extractedTactics?: string[];
  };
}

export interface StorageStats {
  totalFlows: number;
  storageUsed: number; // bytes
  oldestFlow?: string;
  newestFlow?: string;
  averageNodes?: number;
  averageEdges?: number;
}

export interface FlowSearchFilters {
  searchTerm: string;
  tags: string[];
  confidence?: 'low' | 'medium' | 'high';
  dateRange?: {
    start: string;
    end: string;
  };
  sortBy: 'date' | 'title' | 'nodes' | 'confidence';
  sortOrder: 'asc' | 'desc';
}

export interface ImportResult {
  success: SavedFlow[];
  failed: Array<{
    filename: string;
    error: string;
  }>;
  duplicates: Array<{
    existing: SavedFlow;
    imported: SavedFlow;
  }>;
}

// Common flow tags for UI suggestions
export const COMMON_TAGS = [
  'apt',
  'ransomware',
  'phishing',
  'malware',
  'vulnerability',
  'persistence',
  'lateral-movement',
  'data-exfiltration',
  'command-control',
  'initial-access',
  'privilege-escalation',
  'defense-evasion',
  'credential-access',
  'discovery',
  'collection',
  'impact'
] as const;

export type CommonTag = typeof COMMON_TAGS[number];