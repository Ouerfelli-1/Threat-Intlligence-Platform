/**
 * Typed API client for the TIP platform.
 * All calls go through the Next.js BFF at /api/* which proxies to backend services.
 */

import { useStore } from './store';

const BASE = '/api';

class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

// Single-flight redirect — if a /me poll, an SWR hook, and a manual call
// all 401 at the same moment, we only redirect ONCE. Avoids the user
// seeing "missing bearer token" toasts spam while the redirect happens.
let redirecting = false;
function redirectToLogin() {
  if (redirecting) return;
  redirecting = true;
  try { useStore.getState().clearAuth(); } catch { /* SSR */ }
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts?: { params?: Record<string, string | number | boolean | undefined> }
): Promise<T> {
  // Block requests before zustand hydrates with a token. Without this we'd
  // fire calls with no Authorization header on every first paint, get back
  // a parade of 401s, and surface them as "missing bearer token" errors
  // in the UI before the layout's redirect-on-no-token kicks in.
  const token = useStore.getState().token;
  if (!token) {
    redirectToLogin();
    throw new ApiError(401, 'no-token');  // SWR will treat as error; the
                                          // redirect already fired so the
                                          // user lands on /login anyway.
  }

  const url = new URL(`${BASE}${path}`, window.location.origin);

  if (opts?.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      if (v !== undefined && v !== null && v !== '') {
        url.searchParams.set(k, String(v));
      }
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  };

  const res = await fetch(url.toString(), {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    // Token expired / session revoked. Quietly clear + redirect; do NOT
    // bubble the "missing bearer token" string into UI toasts.
    redirectToLogin();
    throw new ApiError(401, 'session-expired');
  }

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new ApiError(res.status, errBody);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>('GET', path, undefined, { params }),
  post: <T>(path: string, body?: unknown) =>
    request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) =>
    request<T>('PATCH', path, body),
  put: <T>(path: string, body?: unknown) =>
    request<T>('PUT', path, body),
  delete: <T>(path: string) =>
    request<T>('DELETE', path),
};

// SWR fetcher
export const fetcher = <T>(path: string): Promise<T> => api.get<T>(path);
