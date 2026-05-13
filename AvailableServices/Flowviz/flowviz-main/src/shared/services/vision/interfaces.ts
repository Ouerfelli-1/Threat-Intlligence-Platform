import { ImageInfo, VisionAnalysisResult } from './types';

export interface IVisionPromptBuilder {
  buildPrompt(articleText: string, imageCount: number): string;
}

export interface IVisionMessageBuilder {
  buildMessageContent(images: ImageInfo[], prompt: string): Promise<any[]>;
}

export interface IVisionConfidenceAssessor {
  assessConfidence(analysisText: string, imageCount: number): 'low' | 'medium' | 'high';
}

export interface IVisionTextCombiner {
  combineTextAndVision(articleText: string, visionResult: VisionAnalysisResult): string;
}

export interface IVisionAnalyzer {
  analyzeImages(images: ImageInfo[], articleText: string): Promise<VisionAnalysisResult>;
}