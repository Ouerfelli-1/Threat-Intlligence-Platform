/// <reference types="vite/client" />

// REMOVED: VITE_ANTHROPIC_API_KEY no longer used - all API calls are server-side only
interface ImportMetaEnv {
  // No client-side API keys - all authentication handled server-side
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
} 