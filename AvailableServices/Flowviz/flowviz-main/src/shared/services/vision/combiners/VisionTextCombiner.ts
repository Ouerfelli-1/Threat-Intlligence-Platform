import { IVisionTextCombiner } from '../interfaces';
import { VisionAnalysisResult } from '../types';

export class VisionTextCombiner implements IVisionTextCombiner {
  combineTextAndVision(articleText: string, visionResult: VisionAnalysisResult): string {
    if (!visionResult.analysisText) {
      return articleText;
    }
    
    console.log('=== COMBINING TEXT AND VISION ANALYSIS ===');
    console.log(`Original text: ${articleText.length} chars`);
    console.log(`Vision analysis: ${visionResult.analysisText.length} chars`);
    console.log(`Vision confidence: ${visionResult.confidence}`);
    
    // Combine with clear separation
    const combinedContent = this.buildCombinedContent(articleText, visionResult);

    console.log(`Combined content: ${combinedContent.length} chars`);
    
    return combinedContent;
  }

  private buildCombinedContent(articleText: string, visionResult: VisionAnalysisResult): string {
    return `${articleText}

=== VISUAL ANALYSIS FROM IMAGES ===
${visionResult.analysisText}`;
  }
}