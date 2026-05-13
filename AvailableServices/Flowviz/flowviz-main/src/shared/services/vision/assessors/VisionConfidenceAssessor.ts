import { IVisionConfidenceAssessor } from '../interfaces';
import { VISION_PROMPT_CONFIG, CONFIDENCE_THRESHOLDS } from '../config';

export class VisionConfidenceAssessor implements IVisionConfidenceAssessor {
  assessConfidence(analysisText: string, imageCount: number): 'low' | 'medium' | 'high' {
    if (!analysisText || analysisText.length < CONFIDENCE_THRESHOLDS.medium.minTextLength) {
      return 'low';
    }
    
    // Count technical indicators in the analysis
    const indicatorCount = this.countTechnicalIndicators(analysisText);
    
    // Assess based on indicators, image count, and text length
    if (this.meetsHighConfidenceThreshold(indicatorCount, imageCount, analysisText.length)) {
      return 'high';
    } else if (this.meetsMediumConfidenceThreshold(indicatorCount, imageCount, analysisText.length)) {
      return 'medium';
    } else {
      return 'low';
    }
  }

  private countTechnicalIndicators(analysisText: string): number {
    return VISION_PROMPT_CONFIG.technicalIndicators.reduce((count, pattern) => {
      return count + (pattern.test(analysisText) ? 1 : 0);
    }, 0);
  }

  private meetsHighConfidenceThreshold(indicatorCount: number, imageCount: number, textLength: number): boolean {
    const { high } = CONFIDENCE_THRESHOLDS;
    return indicatorCount >= high.minIndicators && 
           imageCount >= high.minImages && 
           textLength >= high.minTextLength;
  }

  private meetsMediumConfidenceThreshold(indicatorCount: number, imageCount: number, textLength: number): boolean {
    const { medium } = CONFIDENCE_THRESHOLDS;
    return indicatorCount >= medium.minIndicators && 
           imageCount >= medium.minImages && 
           textLength >= medium.minTextLength;
  }
}