// Re-define ImageInfo to avoid circular import issues
export interface ImageInfo {
  src: string;
  alt?: string;
  title?: string;
  base64Data?: string;
  mediaType: string;
  size?: {
    width?: number;
    height?: number;
  };
  relevanceScore?: number;
}

export interface VisionAnalysisResult {
  relevantImages: ImageInfo[];
  analysisText: string;
  confidence: 'low' | 'medium' | 'high';
}

export interface VisionAnalysisConfig {
  model: string;
  maxTokens: number;
  temperature: number;
  timeout: number;
  thinking?: {
    type: 'enabled';
    budget_tokens: number;
  };
}

export interface VisionPromptConfig {
  maxContextLength: number;
  includeImageLabels: boolean;
  technicalIndicators: RegExp[];
}

// ImageInfo is now defined above