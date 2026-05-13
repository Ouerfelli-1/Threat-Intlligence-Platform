export const API_CONFIG = {
  baseURL: 'https://api.anthropic.com',
  model: 'claude-sonnet-4-20250514',
  maxTokens: 16000, // Model supports higher token limits
  temperature: 0.1, // Restored for deterministic output
} as const;

export const RETRY_CONFIG = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 10000,
} as const;

export const PROCESSING_CONFIG = {
  // Model has 200k token input limit (~800k characters)
  // Setting to 700k chars to leave buffer for prompts and system messages
  maxChunkSize: 700000,
  systemPrompt: "You are an expert in cyber threat intelligence and MITRE ATT&CK. Your task is to analyze articles and images to extract detailed attack flow information. You must ONLY respond with a valid JSON object matching the specified structure exactly. Do not include any other text or explanations.",
} as const;

export const TACTIC_DEFINITIONS = [
  { key: 'initialAccess', prefix: 'initial', tacticId: 'TA0001' },
  { key: 'execution', prefix: 'exec', tacticId: 'TA0002' },
  { key: 'persistence', prefix: 'persist', tacticId: 'TA0003' },
  { key: 'privilegeEscalation', prefix: 'priv', tacticId: 'TA0004' },
  { key: 'defenseEvasion', prefix: 'defense', tacticId: 'TA0005' },
  { key: 'credentialAccess', prefix: 'cred', tacticId: 'TA0006' },
  { key: 'discovery', prefix: 'discovery', tacticId: 'TA0007' },
  { key: 'lateralMovement', prefix: 'lateral', tacticId: 'TA0008' },
  { key: 'collection', prefix: 'collect', tacticId: 'TA0009' },
  { key: 'commandAndControl', prefix: 'c2', tacticId: 'TA0011' },
  { key: 'exfiltration', prefix: 'exfil', tacticId: 'TA0010' },
  { key: 'impact', prefix: 'impact', tacticId: 'TA0040' },
] as const;