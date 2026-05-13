import { IImageExtractor } from '../interfaces';
import { ImageInfo } from '../types';
import { IMAGE_FILTER_CONFIG, MEDIA_TYPE_MAP } from '../config';

export class ImageExtractor implements IImageExtractor {
  extractImages(doc: Document, baseUrl?: string): ImageInfo[] {
    const images: ImageInfo[] = [];
    const imgElements = doc.querySelectorAll('img');
    
    console.log(`Found ${imgElements.length} images in the document`);
    
    imgElements.forEach((img, index) => {
      const imageInfo = this.processImageElement(img, baseUrl, index);
      if (imageInfo) {
        images.push(imageInfo);
      }
    });
    
    return images;
  }

  private processImageElement(img: HTMLImageElement, baseUrl?: string, index?: number): ImageInfo | null {
    const src = img.src || img.getAttribute('src');
    if (!src) return null;
    
    // Resolve relative URLs
    const fullSrc = this.resolveImageUrl(src, baseUrl);
    if (!fullSrc) return null;
    
    // Skip very small images (likely icons/decorations)
    if (this.isImageTooSmall(img)) {
      console.log(`Skipping small image: ${fullSrc} (${img.width}x${img.height})`);
      return null;
    }
    
    // Skip common non-content images
    if (this.isDecorativeImage(fullSrc, img)) {
      console.log(`Skipping decorative image: ${fullSrc}`);
      return null;
    }
    
    // Skip localhost images (they won't be accessible to the server)
    if (fullSrc.includes('localhost') || fullSrc.includes('127.0.0.1')) {
      console.log(`Skipping localhost image: ${fullSrc}`);
      return null;
    }
    
    const imageInfo: ImageInfo = {
      src: fullSrc,
      alt: img.alt || undefined,
      title: img.title || undefined,
      mediaType: this.getImageMediaType(fullSrc),
      size: {
        width: img.width > 0 ? img.width : undefined,
        height: img.height > 0 ? img.height : undefined,
      }
    };
    
    console.log(`Extracted image ${(index || 0) + 1}: ${fullSrc} (alt: "${imageInfo.alt || 'none'}")`);
    return imageInfo;
  }

  private resolveImageUrl(src: string, baseUrl?: string): string | null {
    if (src.startsWith('http')) {
      return src;
    }
    
    if (!baseUrl) {
      return src.startsWith('/') ? src : null;
    }
    
    try {
      return new URL(src, baseUrl).href;
    } catch (e) {
      console.warn(`Could not resolve image URL: ${src}`);
      return null;
    }
  }

  private isImageTooSmall(img: HTMLImageElement): boolean {
    const width = parseInt(img.getAttribute('width') || '0') || img.width;
    const height = parseInt(img.getAttribute('height') || '0') || img.height;
    
    return (width > 0 && width < IMAGE_FILTER_CONFIG.minWidth) || 
           (height > 0 && height < IMAGE_FILTER_CONFIG.minHeight);
  }

  private isDecorativeImage(src: string, img: HTMLImageElement): boolean {
    return IMAGE_FILTER_CONFIG.skipPatterns.some(pattern => 
      pattern.test(src) || 
      pattern.test(img.alt || '') || 
      pattern.test(img.className)
    );
  }

  private getImageMediaType(url: string): string {
    // Remove query parameters and fragments first
    const cleanUrl = url.split('?')[0].split('#')[0];
    const extension = cleanUrl.split('.').pop()?.toLowerCase() as keyof typeof MEDIA_TYPE_MAP;
    return MEDIA_TYPE_MAP[extension] || 'image/jpeg';
  }
}