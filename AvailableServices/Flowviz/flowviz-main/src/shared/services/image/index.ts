// Main exports
export { ImageProcessor } from './ImageProcessor';

// Type exports
export * from './types';
export * from './interfaces';

// Service factory for easy instantiation
import { ImageProcessor } from './ImageProcessor';
import { ImageExtractor } from './extractors/ImageExtractor';
import { ImageFilter } from './filters/ImageFilter';
import { ImageDownloader } from './downloaders/ImageDownloader';
import { ImageOptimizer } from './optimizers/ImageOptimizer';

// Factory function to create a fully configured ImageProcessor
export function createImageProcessor(): ImageProcessor {
  const imageExtractor = new ImageExtractor();
  const imageFilter = new ImageFilter();
  const imageDownloader = new ImageDownloader();
  const imageOptimizer = new ImageOptimizer();
  
  return new ImageProcessor(
    imageExtractor,
    imageFilter,
    imageDownloader,
    imageOptimizer
  );
}

// Backward compatibility exports
export function extractImagesFromHTML(doc: Document, baseUrl?: string) {
  const processor = createImageProcessor();
  return processor.extractImages(doc, baseUrl);
}

export function filterRelevantImages(images: any[]) {
  const processor = createImageProcessor();
  return processor.filterRelevantImages(images);
}

export async function downloadImageAsBase64(imageInfo: any): Promise<string> {
  const processor = createImageProcessor();
  return processor.downloadAsBase64(imageInfo);
}

export function optimizeImageSize(base64Data: string, mediaType: string): string {
  const processor = createImageProcessor();
  return processor.optimizeSize(base64Data, mediaType);
}

export function estimateImageTokens(images: any[]): number {
  const processor = createImageProcessor();
  return processor.estimateTokens(images);
}