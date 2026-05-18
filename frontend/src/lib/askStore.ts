/**
 * Persisted Zustand store for Ask AI chat sessions.
 * Sessions survive tab switches and browser restarts (localStorage).
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AskResult {
  id?: string;
  status?: string;
  response?: string;
  rationale?: string;
  recommended_actions?: string[];
  related_cves?: string[];
  related_actors?: string[];
  related_iocs?: string[];
  sources_consulted?: string[];
  payload?: Record<string, unknown>;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  result?: AskResult;
  timestamp: number;
}

export interface ChatSession {
  id: string;
  title: string;          // first user message, truncated to 60 chars
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

interface AskStore {
  currentSessionId: string | null;
  sessions: ChatSession[];

  /** Messages for the active session (empty array if no session). */
  getCurrentMessages: () => ChatMessage[];

  /**
   * Append a message to the current session.
   * Creates a new session automatically if none is active.
   * Returns the session ID that was used.
   */
  addMessage: (msg: ChatMessage) => string;

  /**
   * Update the last assistant message in a specific session.
   * Used by the polling callback so it targets the right session
   * even if the user switched sessions after sending.
   */
  updateLastAssistantMessage: (
    sessionId: string,
    updater: (m: ChatMessage) => ChatMessage,
  ) => void;

  /** Deselect the current session (shows blank state). Does NOT delete anything. */
  startNewSession: () => void;

  /** Switch the active session. */
  loadSession: (id: string) => void;

  /** Permanently delete a session. */
  deleteSession: (id: string) => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function genId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function sessionTitle(text: string): string {
  const t = text.trim();
  return t.length > 60 ? t.slice(0, 60) + '…' : t;
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useAskStore = create<AskStore>()(
  persist(
    (set, get) => ({
      currentSessionId: null,
      sessions: [],

      getCurrentMessages: () => {
        const { currentSessionId, sessions } = get();
        if (!currentSessionId) return [];
        return sessions.find(s => s.id === currentSessionId)?.messages ?? [];
      },

      addMessage: (msg: ChatMessage): string => {
        let usedId = '';

        set(state => {
          let { currentSessionId } = state;
          let sessions = [...state.sessions];

          if (!currentSessionId) {
            // ── Create a brand-new session ──────────────────────────────────
            const id = genId();
            const title =
              msg.role === 'user' ? sessionTitle(msg.content) : 'New conversation';
            sessions = [
              {
                id,
                title,
                messages: [msg],
                createdAt: msg.timestamp,
                updatedAt: msg.timestamp,
              },
              ...sessions,
            ];
            usedId = id;
            return { sessions, currentSessionId: id };
          }

          // ── Append to existing session ──────────────────────────────────
          usedId = currentSessionId;
          sessions = sessions.map(s => {
            if (s.id !== currentSessionId) return s;
            const isFirst = s.messages.length === 0;
            return {
              ...s,
              title:
                isFirst && msg.role === 'user'
                  ? sessionTitle(msg.content)
                  : s.title,
              messages: [...s.messages, msg],
              updatedAt: msg.timestamp,
            };
          });
          return { sessions };
        });

        return usedId;
      },

      updateLastAssistantMessage: (sessionId, updater) => {
        set(state => ({
          sessions: state.sessions.map(s => {
            if (s.id !== sessionId) return s;
            const msgs = [...s.messages];
            for (let i = msgs.length - 1; i >= 0; i--) {
              if (msgs[i].role === 'assistant') {
                msgs[i] = updater(msgs[i]);
                break;
              }
            }
            return { ...s, messages: msgs, updatedAt: Date.now() };
          }),
        }));
      },

      startNewSession: () => set({ currentSessionId: null }),

      loadSession: (id: string) => set({ currentSessionId: id }),

      deleteSession: (id: string) =>
        set(state => ({
          sessions: state.sessions.filter(s => s.id !== id),
          currentSessionId:
            state.currentSessionId === id ? null : state.currentSessionId,
        })),
    }),
    { name: 'tip-ask-v1', version: 1 },
  ),
);

// ─── Date-grouping helper (used by the sidebar) ───────────────────────────────

export type SessionGroup = {
  label: string;
  sessions: ChatSession[];
};

export function groupSessionsByDate(sessions: ChatSession[]): SessionGroup[] {
  const now = Date.now();
  const DAY = 86_400_000;

  const groups: SessionGroup[] = [
    { label: 'Today', sessions: [] },
    { label: 'Yesterday', sessions: [] },
    { label: 'This week', sessions: [] },
    { label: 'Older', sessions: [] },
  ];

  for (const s of sessions) {
    const age = now - s.updatedAt;
    if (age < DAY) groups[0].sessions.push(s);
    else if (age < 2 * DAY) groups[1].sessions.push(s);
    else if (age < 7 * DAY) groups[2].sessions.push(s);
    else groups[3].sessions.push(s);
  }

  return groups.filter(g => g.sessions.length > 0);
}
