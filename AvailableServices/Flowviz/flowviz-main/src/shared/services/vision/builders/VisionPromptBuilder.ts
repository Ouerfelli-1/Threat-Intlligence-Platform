import { IVisionPromptBuilder } from '../interfaces';
import { VISION_PROMPT_TEMPLATE, VISION_PROMPT_CONFIG } from '../config';

export class VisionPromptBuilder implements IVisionPromptBuilder {
  buildPrompt(articleText: string, imageCount: number): string {
    const articleContext = this.truncateArticleContext(articleText);
    
    return VISION_PROMPT_TEMPLATE
      .replace('{imageCount}', imageCount.toString())
      .replace('{articleContext}', articleContext);
  }

  private truncateArticleContext(articleText: string): string {
    if (articleText.length <= VISION_PROMPT_CONFIG.maxContextLength) {
      return articleText;
    }
    
    const truncated = articleText.substring(0, VISION_PROMPT_CONFIG.maxContextLength);
    return truncated + (articleText.length > VISION_PROMPT_CONFIG.maxContextLength ? '...' : '');
  }
}