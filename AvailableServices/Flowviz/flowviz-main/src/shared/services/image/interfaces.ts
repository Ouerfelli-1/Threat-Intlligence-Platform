import { ImageInfo } from './types';

export interface IImageExtractor {
  extractImages(doc: Document, baseUrl?: string): ImageInfo[];
}

export interface IImageFilter {
  filterRelevantImages(images: ImageInfo[]): ImageInfo[];
}

export interface IImageDownloader {
  downloadAsBase64(imageInfo: ImageInfo): Promise<string>;
  downloadMultiple(images: ImageInfo[]): Promise<ImageInfo[]>;
}

export interface IImageOptimizer {
  optimizeSize(base64Data: string, mediaType: string): string;
  estimateTokens(images: ImageInfo[]): number;
}

export interface IImageProcessor {
  extractImages(doc: Document, baseUrl?: string): ImageInfo[];
  filterRelevantImages(images: ImageInfo[]): ImageInfo[];
  downloadAsBase64(imageInfo: ImageInfo): Promise<string>;
  optimizeSize(base64Data: string, mediaType: string): string;
  estimateTokens(images: ImageInfo[]): number;
}