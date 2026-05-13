import { IVisionMessageBuilder } from '../interfaces';
import { ImageInfo } from '../types';
import { VISION_PROMPT_CONFIG } from '../config';

export class VisionMessageBuilder implements IVisionMessageBuilder {
  async buildMessageContent(images: ImageInfo[], prompt: string): Promise<any[]> {
    const content: any[] = [];
    
    // Add images first (recommended by vision API docs)
    this.addImagesToContent(content, images);
    
    // Add the analysis prompt
    content.push({
      type: 'text',
      text: prompt
    });
    
    return content;
  }

  private addImagesToContent(content: any[], images: ImageInfo[]): void {
    for (let i = 0; i < images.length; i++) {
      const image = images[i];
      
      // Add image label for multiple images
      if (images.length > 1 && VISION_PROMPT_CONFIG.includeImageLabels) {
        content.push({
          type: 'text',
          text: `Image ${i + 1}:`
        });
      }
      
      // Vision API requires base64 for images, not URLs
      if (image.base64Data) {
        content.push({
          type: 'image',
          source: {
            type: 'base64',
            media_type: image.mediaType,
            data: image.base64Data
          }
        });
        console.log(`Using base64 for image ${i + 1} (${image.base64Data.length} chars)`);
      } else {
        console.warn(`Skipping image ${i + 1}: no base64 data available`);
      }
    }
  }
}