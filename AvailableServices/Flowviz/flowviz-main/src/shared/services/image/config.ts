import { ImageFilterConfig, ImageDownloadConfig, ImageOptimizationConfig } from './types';

export const IMAGE_FILTER_CONFIG: ImageFilterConfig = {
  maxImages: 5,
  minWidth: 50,
  minHeight: 50,
  skipPatterns: [
    /favicon/i,
    /logo/i,
    /icon/i,
    /avatar/i,
    /profile/i,
    /social/i,
    /share/i,
    /button/i,
    /arrow/i,
    /pixel\.gif/i,
    /\.gif$/i // Skip all gifs for now (often animations/decorations)
  ],
  highRelevanceTerms: [
    'attack', 'malware', 'vulnerability', 'exploit', 'hack', 'breach',
    'phishing', 'ransomware', 'trojan', 'virus', 'backdoor',
    'command', 'terminal', 'console', 'shell', 'code',
    'network', 'diagram', 'topology', 'infrastructure',
    'screenshot', 'capture', 'analysis', 'forensic',
    'threat', 'apt', 'campaign', 'ioc', 'indicator'
  ],
  mediumRelevanceTerms: [
    'security', 'cyber', 'system', 'server', 'database',
    'login', 'credential', 'password', 'authentication',
    'flow', 'process', 'workflow', 'technique', 'method',
    'tool', 'software', 'application', 'platform'
  ]
} as const;

export const IMAGE_DOWNLOAD_CONFIG: ImageDownloadConfig = {
  apiEndpoint: '/api/fetch-image',
  timeout: 10000, // 10 seconds
  maxRetries: 3
} as const;

export const IMAGE_OPTIMIZATION_CONFIG: ImageOptimizationConfig = {
  maxFileSize: 20 * 1024 * 1024, // 20MB
  maxWidth: 1024,
  maxHeight: 1024,
  quality: 0.8
} as const;

export const MEDIA_TYPE_MAP = {
  'jpg': 'image/jpeg',
  'jpeg': 'image/jpeg',
  'png': 'image/png',
  'gif': 'image/gif',
  'webp': 'image/webp'
} as const;

export const TOKEN_ESTIMATION = {
  averageTokensPerImage: 1334 // Conservative estimate for 1000x1000px image
} as const;