import { IImageFilter } from '../interfaces';
import { ImageInfo } from '../types';
import { IMAGE_FILTER_CONFIG } from '../config';

export class ImageFilter implements IImageFilter {
  filterRelevantImages(images: ImageInfo[]): ImageInfo[] {
    // Score images based on relevance
    const scoredImages = images.map(img => ({
      ...img,
      relevanceScore: this.calculateRelevanceScore(img)
    }));
    
    // Filter and sort by relevance score
    const relevantImages = scoredImages
      .filter(img => img.relevanceScore > 0)
      .sort((a, b) => b.relevanceScore - a.relevanceScore);
    
    this.logRelevanceScores(relevantImages);
    
    // Return top candidates to avoid token limits
    return relevantImages.slice(0, IMAGE_FILTER_CONFIG.maxImages);
  }

  private calculateRelevanceScore(img: ImageInfo): number {
    let score = 0;
    const alt = (img.alt || '').toLowerCase();
    const title = (img.title || '').toLowerCase();
    
    // Check for high relevance terms
    IMAGE_FILTER_CONFIG.highRelevanceTerms.forEach(term => {
      if (alt.includes(term) || title.includes(term)) {
        score += 3;
      }
    });
    
    // Check for medium relevance terms
    IMAGE_FILTER_CONFIG.mediumRelevanceTerms.forEach(term => {
      if (alt.includes(term) || title.includes(term)) {
        score += 1;
      }
    });
    
    // Prefer larger images (more likely to contain detailed info)
    if (img.size?.width && img.size.width > 400) score += 1;
    if (img.size?.height && img.size.height > 300) score += 1;
    
    // Prefer certain file types
    if (img.mediaType === 'image/png') score += 1; // PNG often used for screenshots
    
    return score;
  }

  private logRelevanceScores(scoredImages: ImageInfo[]): void {
    console.log('Image relevance scores:');
    scoredImages.forEach(img => {
      console.log(`- ${img.src} (score: ${img.relevanceScore}, alt: "${img.alt || 'none'}")`);
    });
  }
}