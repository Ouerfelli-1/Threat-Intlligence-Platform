// REMOVED: VisionAnalyzer - now handled server-side via /api/vision-analysis

// Type exports only
export * from './types';
export * from './interfaces';

// Only text combiner utility remains (no API usage)
import { VisionTextCombiner } from './combiners/VisionTextCombiner';

export function createVisionTextCombiner(): VisionTextCombiner {
  return new VisionTextCombiner();
}

// REMOVED: Client-side vision analysis functions - now server-side only