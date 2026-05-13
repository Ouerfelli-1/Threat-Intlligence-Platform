import { VisionAnalysisConfig, VisionPromptConfig } from './types';

export const VISION_ANALYSIS_CONFIG: VisionAnalysisConfig = {
  model: 'claude-sonnet-4-20250514',
  maxTokens: 8000, // Claude 4 supports higher limits for vision
  temperature: 0.1, // Restored for deterministic output
  timeout: 30000, // 30 seconds
} as const;

export const VISION_PROMPT_CONFIG: VisionPromptConfig = {
  maxContextLength: 2000,
  includeImageLabels: true,
  technicalIndicators: [
    /command/i, 
    /powershell/i, 
    /cmd/i, 
    /bash/i,
    /malware/i, 
    /payload/i, 
    /exploit/i,
    /ip address/i, 
    /domain/i, 
    /url/i, 
    /hash/i,
    /T\d{4}/i, // MITRE technique IDs
    /CVE-\d{4}-\d+/i, // CVE references
  ]
} as const;

export const VISION_PROMPT_TEMPLATE = `You are analyzing {imageCount} image(s) from a cybersecurity article to extract attack technique information that complements the text content.

ARTICLE TEXT CONTEXT:
{articleContext}

VISION ANALYSIS INSTRUCTIONS:
Analyze the provided image(s) and extract any cybersecurity-related information that would be valuable for understanding attack techniques, tools, or processes. Focus on:

1. **Command Line Screenshots**: Extract exact commands, parameters, file paths, URLs, and tool usage
2. **Network Diagrams**: Identify infrastructure, attack paths, communication flows, and targeted systems  
3. **Tool Interfaces**: Document tool names, configurations, attack parameters, and usage patterns
4. **Code/Scripts**: Extract malicious code, PowerShell commands, SQL injections, or exploit code
5. **Attack Flow Diagrams**: Identify attack stages, techniques, and decision points
6. **System Screenshots**: Document compromised systems, file structures, registry changes, or evidence
7. **Indicators of Compromise**: Extract IP addresses, domains, file hashes, registry keys, or artifacts

For each image, provide:
- **Image Description**: What the image shows (1-2 sentences)
- **Extracted Technical Details**: Specific commands, tools, indicators, or technical information
- **Attack Relevance**: How this relates to MITRE ATT&CK techniques or attack flow
- **Confidence Level**: High/Medium/Low based on image clarity and information value

IMPORTANT: 
- Extract EXACT text from screenshots (commands, URLs, file paths, etc.)
- Identify specific tool names, versions, and configurations
- Note any MITRE technique IDs or references visible in the images
- If multiple images show the same attack stage, consolidate the information

Provide your analysis in clear, structured text that can be combined with the article text for attack flow generation.`;

export const CONFIDENCE_THRESHOLDS = {
  high: {
    minIndicators: 3,
    minImages: 2,
    minTextLength: 200
  },
  medium: {
    minIndicators: 2,
    minImages: 1,
    minTextLength: 100
  },
  low: {
    minIndicators: 0,
    minImages: 0,
    minTextLength: 0
  }
} as const;