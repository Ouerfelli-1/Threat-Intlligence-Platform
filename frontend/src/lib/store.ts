import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  username: string;
  role: string;
  permissions: string[];
}

interface AuthState {
  token: string | null;
  user: User | null;
  sidebarCollapsed: boolean;
  setAuth: (token: string, user: User) => void;
  clearAuth: () => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
}

export const useStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      sidebarCollapsed: false,
      setAuth: (token, user) => set({ token, user }),
      clearAuth: () => set({ token: null, user: null }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
    }),
    { name: 'tip-auth' }
  )
);


/* ── Permission helpers ─────────────────────────────────────────────────────
 *
 * Backend RBAC: every endpoint guards itself with require_permission(perm),
 * where `perm` is a string like "assets:write" or "secrets:read". The JWT
 * carries `perms: string[]` and the /me endpoint returns the same. Admin
 * roles carry the wildcard "*".
 *
 * These helpers mirror the same logic on the client so we can hide UI we
 * know would 403 — the backend remains the source of truth, but the
 * navigation chrome shouldn't dangle "Users & Roles" links for a viewer.
 *
 * Rules:
 *   - "*"          -> matches anything (admin).
 *   - "resource:*" -> matches every "resource:<verb>".
 *   - exact match  -> "assets:write" matches "assets:write".
 */
export function permissionMatches(granted: string, required: string): boolean {
  if (granted === '*') return true;
  if (granted === required) return true;
  if (granted.endsWith(':*')) {
    const res = granted.slice(0, -2);
    return required.startsWith(res + ':');
  }
  return false;
}

export function hasPermission(user: { permissions?: string[] } | null | undefined, required: string): boolean {
  if (!user || !user.permissions) return false;
  return user.permissions.some((p) => permissionMatches(p, required));
}

/** Admin = holds the "*" wildcard. Concrete check used by Sidebar / Topbar. */
export function isAdmin(user: { permissions?: string[] } | null | undefined): boolean {
  return !!user?.permissions?.includes('*');
}

/** Hook variants — read live from the store. */
export function useHasPermission(required: string): boolean {
  const user = useStore((s) => s.user);
  return hasPermission(user, required);
}

export function useIsAdmin(): boolean {
  const user = useStore((s) => s.user);
  return isAdmin(user);
}
