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

export interface ImageAnalysisResult {
  relevantImages: ImageInfo[];
  analysisText: string;
  confidence: 'low' | 'medium' | 'high';
}

export interface ImageFilterConfig {
  maxImages: number;
  minWidth: number;
  minHeight: number;
  skipPatterns: RegExp[];
  highRelevanceTerms: string[];
  mediumRelevanceTerms: string[];
}

export interface ImageDownloadConfig {
  apiEndpoint: string;
  timeout: number;
  maxRetries: number;
}

export interface ImageOptimizationConfig {
  maxFileSize: number;
  maxWidth: number;
  maxHeight: number;
  quality: number;
}