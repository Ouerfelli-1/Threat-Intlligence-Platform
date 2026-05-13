import { IImageProcessor, IImageExtractor, IImageFilter, IImageDownloader, IImageOptimizer } from './interfaces';
import { ImageInfo } from './types';

export class ImageProcessor implements IImageProcessor {
  constructor(
    private readonly imageExtractor: IImageExtractor,
    private readonly imageFilter: IImageFilter,
    private readonly imageDownloader: IImageDownloader,
    private readonly imageOptimizer: IImageOptimizer
  ) {}

  extractImages(doc: Document, baseUrl?: string): ImageInfo[] {
    return this.imageExtractor.extractImages(doc, baseUrl);
  }

  filterRelevantImages(images: ImageInfo[]): ImageInfo[] {
    return this.imageFilter.filterRelevantImages(images);
  }

  async downloadAsBase64(imageInfo: ImageInfo): Promise<string> {
    return this.imageDownloader.downloadAsBase64(imageInfo);
  }

  async downloadMultiple(images: ImageInfo[]): Promise<ImageInfo[]> {
    return this.imageDownloader.downloadMultiple(images);
  }

  optimizeSize(base64Data: string, mediaType: string): string {
    return this.imageOptimizer.optimizeSize(base64Data, mediaType);
  }

  estimateTokens(images: ImageInfo[]): number {
    return this.imageOptimizer.estimateTokens(images);
  }

  // Convenience method for full processing pipeline
  async processImages(doc: Document, baseUrl?: string): Promise<ImageInfo[]> {
    console.log('=== IMAGE PROCESSOR: Starting full processing pipeline ===');
    
    // Step 1: Extract all images
    const allImages = this.extractImages(doc, baseUrl);
    console.log(`Extracted ${allImages.length} images`);
    
    if (allImages.length === 0) {
      return [];
    }
    
    // Step 2: Filter for relevance
    const relevantImages = this.filterRelevantImages(allImages);
    console.log(`Filtered to ${relevantImages.length} relevant images`);
    
    if (relevantImages.length === 0) {
      return [];
    }
    
    // Step 3: Download images
    const downloadedImages = await this.downloadMultiple(relevantImages);
    console.log(`Downloaded ${downloadedImages.length} images successfully`);
    
    // Step 4: Optimize if needed (future enhancement)
    // const optimizedImages = downloadedImages.map(img => {
    //   if (img.base64Data) {
    //     img.base64Data = this.optimizeSize(img.base64Data, img.mediaType);
    //   }
    //   return img;
    // });
    
    return downloadedImages;
  }
}