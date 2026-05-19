'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Plus, Sparkles, Paperclip, Layers, Send,
  Refresh, X, Trash, MessageSquare,
} from '@/components/icons';
import { useStore } from '@/lib/store';
import {
  useAskStore,
  groupSessionsByDate,
  type AskResult,
  type ChatMessage,
} from '@/lib/askStore';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function fmtDate(ts: number): string {
  return new Date(ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

// ─── Result card ──────────────────────────────────────────────────────────────

function ResultCard({ result }: { result: AskResult }) {
  // The orchestrator /ask endpoint returns AskOutput which has `answer` not `response`
  const response = result.response ?? result.rationale ?? (result as Record<string, unknown>).answer as string ?? null;
  const supporting = ((result as Record<string, unknown>).supporting_evidence as string[] | undefined) ?? [];
  const caveats  = ((result as Record<string, unknown>).caveats as string[] | undefined) ?? [];
  const actions  = result.recommended_actions ?? [];
  const cves     = result.related_cves ?? [];
  const actors   = result.related_actors ?? [];
  const iocs     = result.related_iocs ?? [];
  const sources  = result.sources_consulted ?? [];

  if (result.status === 'running') {
    return (
      <div style={{ padding: 16, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-3)', fontSize: 12.5 }}>
          <Refresh s={13} />
          Analysis running — checking every 3 s. You can switch tabs; the result will be here when you return.
        </div>
      </div>
    );
  }

  if (result.status === 'timeout') {
    return (
      <div style={{ padding: 16, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10 }}>
        <p style={{ fontSize: 13, color: 'var(--text-3)', margin: 0 }}>
          {result.response ?? 'Analysis is still running. Check Operations → Reports for the result.'}
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10 }}>
      {response && (
        <p style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.65, margin: '0 0 12px' }}>{response}</p>
      )}

      {!response && result.payload && (
        <pre style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', margin: '0 0 12px' }}>
          {JSON.stringify(result.payload, null, 2)}
        </pre>
      )}

      {/* Confidence badge intentionally removed (operator dropped numeric
          confidence metrics platform-wide). */}

      {/* Supporting evidence */}
      {supporting.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
            Supporting evidence
          </div>
          {supporting.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, padding: '3px 0', fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5 }}>
              <span style={{ color: 'var(--accent)', fontSize: 10, marginTop: 2 }}>▸</span>{e}
            </div>
          ))}
        </div>
      )}

      {/* Caveats */}
      {caveats.length > 0 && (
        <div style={{ padding: '8px 10px', background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.2)', borderRadius: 6, marginBottom: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Caveats</div>
          {caveats.map((c, i) => (
            <div key={i} style={{ fontSize: 11.5, color: 'var(--text-3)', padding: '2px 0' }}>{c}</div>
          ))}
        </div>
      )}

      {actions.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
            Recommended actions
          </div>
          {actions.map((a, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, padding: '4px 0', fontSize: 12.5, color: 'var(--text-2)' }}>
              <span className="mono" style={{ color: 'var(--accent)', fontSize: 10 }}>P{i + 1}</span>{a}
            </div>
          ))}
        </div>
      )}

      {(cves.length > 0 || actors.length > 0 || iocs.length > 0) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
          {cves.map((c, i) => <span key={i} className="badge crit">{c}</span>)}
          {actors.map((a, i) => <span key={i} className="badge high">{a}</span>)}
          {iocs.map((ioc, i) => <span key={i} className="mono tag" style={{ fontSize: 10.5 }}>{ioc}</span>)}
        </div>
      )}

      {sources.length > 0 && (
        <div style={{ padding: '8px 10px', background: 'var(--bg-elev)', borderRadius: 4, fontSize: 11, color: 'var(--text-3)' }}>
          <strong style={{ color: 'var(--text-2)' }}>Sources:</strong>{' '}
          {sources.join(' · ')}
        </div>
      )}
    </div>
  );
}

// ─── Sessions sidebar ─────────────────────────────────────────────────────────

function SessionSidebar() {
  const {
    sessions, currentSessionId,
    startNewSession, loadSession, deleteSession,
  } = useAskStore();
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const groups = groupSessionsByDate(sessions);

  return (
    <div style={{
      width: 240, minWidth: 240, height: '100%',
      display: 'flex', flexDirection: 'column',
      borderRight: '1px solid var(--border)',
      background: 'var(--bg-elev)',
      overflow: 'hidden',
    }}>
      {/* Sidebar header */}
      <div style={{
        padding: '10px 12px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <MessageSquare s={13} />
        <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>Conversations</span>
        <button
          className="btn sm primary"
          onClick={startNewSession}
          title="New conversation"
          style={{ padding: '3px 8px', fontSize: 11 }}
        >
          <Plus s={11} />New
        </button>
      </div>

      {/* Session list */}
      <div style={{ flex: 1, overflow: 'auto', padding: '6px 4px' }}>
        {sessions.length === 0 && (
          <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
            No conversations yet.<br />Ask something to start.
          </div>
        )}

        {groups.map(group => (
          <div key={group.label}>
            <div style={{
              padding: '8px 10px 4px',
              fontSize: 10, fontWeight: 600,
              color: 'var(--text-4)',
              textTransform: 'uppercase', letterSpacing: '0.08em',
            }}>
              {group.label}
            </div>

            {group.sessions.map(session => {
              const isActive  = session.id === currentSessionId;
              const isHovered = session.id === hoveredId;

              return (
                <div
                  key={session.id}
                  onClick={() => loadSession(session.id)}
                  onMouseEnter={() => setHoveredId(session.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  style={{
                    position: 'relative',
                    display: 'flex', alignItems: 'flex-start', gap: 6,
                    padding: '7px 10px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    background: isActive
                      ? 'var(--accent-bg)'
                      : isHovered
                        ? 'var(--bg-elev2)'
                        : 'transparent',
                    border: isActive
                      ? '1px solid rgba(88,166,255,0.2)'
                      : '1px solid transparent',
                    marginBottom: 1,
                    transition: 'background 0.1s',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 12, color: isActive ? 'var(--accent)' : 'var(--text-2)',
                      fontWeight: isActive ? 600 : 400,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      lineHeight: 1.3,
                    }}>
                      {session.title}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 2 }}>
                      {session.messages.length} msg · {fmtDate(session.updatedAt)}
                    </div>
                  </div>

                  {/* Delete button — visible on hover */}
                  {isHovered && (
                    <button
                      onClick={e => { e.stopPropagation(); deleteSession(session.id); }}
                      title="Delete conversation"
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-4)', padding: '1px 2px',
                        display: 'flex', alignItems: 'center',
                        borderRadius: 3,
                        flexShrink: 0,
                      }}
                      onMouseEnter={e => (e.currentTarget.style.color = 'var(--error)')}
                      onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-4)')}
                    >
                      <Trash s={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AskAIPage() {
  const token = useStore(s => s.token);
  const {
    currentSessionId, sessions,
    addMessage, updateLastAssistantMessage, startNewSession,
  } = useAskStore();

  // Derive messages from the persisted store — survive tab switches
  const messages: ChatMessage[] =
    currentSessionId
      ? (sessions.find(s => s.id === currentSessionId)?.messages ?? [])
      : [];

  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const chatEndRef  = useRef<HTMLDivElement>(null);

  // Auto-scroll when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  // ── Polling for async (202) results ─────────────────────────────────────────
  const pollForResult = useCallback(async (runId: string, sessionId: string) => {
    const maxAttempts = 20; // 20 × 3s = 60s
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/reports/${runId}`, {
          headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        });
        if (res.ok) {
          const report = await res.json();
          if (report?.payload) {
            const result: AskResult = {
              id: runId,
              status: 'complete',
              payload: report.payload,
              response:
                report.payload?.response ??
                report.payload?.headline ??
                report.payload?.summary,
              recommended_actions:
                report.payload?.recommended_actions ??
                report.payload?.top_3_actions?.map((a: Record<string, string>) => a.t ?? a.text) ??
                [],
              related_cves:    report.payload?.related_cves ?? [],
              related_actors:  report.payload?.related_actors ?? [],
              related_iocs:    report.payload?.related_iocs ?? [],
              sources_consulted: report.payload?.sources_consulted ?? [],
            };
            updateLastAssistantMessage(sessionId, m => ({ ...m, result }));
            setLoading(false);
            return;
          }
        }
      } catch { /* continue polling */ }
    }
    // Timed out
    updateLastAssistantMessage(sessionId, m => ({
      ...m,
      result: {
        status: 'timeout',
        response: 'Analysis is still running. Check Operations → Reports for the result.',
      },
    }));
    setLoading(false);
  }, [token, updateLastAssistantMessage]);

  // ── Send ─────────────────────────────────────────────────────────────────────
  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');

    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: Date.now() };
    const sessionId = addMessage(userMsg);
    setLoading(true);

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ question: text, text }),
      });

      if (res.status === 202) {
        const data = await res.json();
        const runningMsg: ChatMessage = {
          role: 'assistant',
          content: '',
          result: { status: 'running', id: data.run_id },
          timestamp: Date.now(),
        };
        addMessage(runningMsg);
        if (data.run_id) {
          // Capture sessionId in closure — polling will update the right session
          // even if the user navigates elsewhere
          pollForResult(data.run_id, sessionId);
        }
        return;
      }

      let result: AskResult = {};
      if (res.ok) {
        const data = await res.json();
        result = {
          ...data,
          response:
            data.response ??
            data.rationale ??
            data.answer ??          // AskOutput returns `answer` not `response`
            data.payload?.response ??
            data.payload?.headline,
          recommended_actions: data.recommended_actions ?? data.payload?.recommended_actions ?? [],
          related_cves:    data.related_cves ?? data.payload?.related_cves ?? [],
          related_actors:  data.related_actors ?? data.payload?.related_actors ?? [],
          related_iocs:    data.related_iocs ?? data.payload?.related_iocs ?? [],
          sources_consulted: data.sources_consulted ?? data.payload?.sources_consulted ?? [],
        };
      } else {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail ?? `HTTP ${res.status}`);
      }

      addMessage({ role: 'assistant', content: '', result, timestamp: Date.now() });
    } catch (e) {
      addMessage({
        role: 'assistant',
        content: `Error: ${e instanceof Error ? e.message : String(e)}`,
        timestamp: Date.now(),
      });
    } finally {
      setLoading(false);
    }
  }, [input, loading, token, addMessage, pollForResult]);

  const suggestions = [
    'Who is most likely to target us right now?',
    'Summarise the latest KEV additions relevant to our stack',
    "What are Cobalt Strike's TTPs and do we have relevant detections?",
    'Draft a board-level brief on ransomware exposure',
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'row', overflow: 'hidden' }}>

      {/* ── Left: sessions sidebar ───────────────────────────────────────── */}
      <SessionSidebar />

      {/* ── Right: chat pane ─────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Header */}
        <div style={{
          padding: '10px 18px',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 8,
          flexShrink: 0,
        }}>
          <Sparkles s={14} />
          <div style={{ fontSize: 14, fontWeight: 600 }}>TIP AI</div>
          {messages.length > 0 && (
            <button className="btn sm" style={{ marginLeft: 'auto' }} onClick={startNewSession}>
              <Plus s={11} />New chat
            </button>
          )}
        </div>

        {/* Chat area */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px' }}>
          <div style={{ maxWidth: 820, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 18 }}>

            {/* Empty state */}
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', paddingTop: 40 }}>
                <Sparkles s={36} />
                <div style={{ fontSize: 20, fontWeight: 600, marginTop: 12, letterSpacing: '-0.015em' }}>
                  What would you like to know?
                </div>
                <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 6 }}>
                  Ask about threats, IOCs, CVEs, actors, or request a brief.<br />
                  The AI reads your live intel graph — not the public internet.
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 20 }}>
                  {suggestions.map(s => (
                    <button key={s} className="btn sm" onClick={() => { setInput(s); textareaRef.current?.focus(); }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map((msg, i) => (
              <div key={i}>
                {msg.role === 'user' && (
                  <div style={{
                    alignSelf: 'flex-end', maxWidth: '85%', marginLeft: 'auto',
                    background: 'var(--accent-bg)',
                    border: '1px solid rgba(88,166,255,0.25)',
                    borderRadius: 10, padding: '10px 14px',
                  }}>
                    <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.5 }}>{msg.content}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 4 }}>{fmtTime(msg.timestamp)}</div>
                  </div>
                )}

                {msg.role === 'assistant' && (
                  <div style={{ maxWidth: '92%' }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                      <Sparkles s={13} />
                      <div style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                        TIP AI · {fmtTime(msg.timestamp)}
                      </div>
                    </div>
                    {msg.content ? (
                      <div style={{
                        padding: 16, background: 'var(--bg-card)',
                        border: '1px solid var(--border)', borderRadius: 10,
                        fontSize: 13, color: 'var(--text-2)', lineHeight: 1.65,
                      }}>
                        {msg.content}
                      </div>
                    ) : msg.result ? (
                      <ResultCard result={msg.result} />
                    ) : null}
                  </div>
                )}
              </div>
            ))}

            {/* Typing indicator — only on the tab that sent the request */}
            {loading && (
              <div style={{ maxWidth: '92%' }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                  <Sparkles s={13} />
                  <div style={{ fontSize: 11.5, color: 'var(--text-3)' }}>TIP AI · thinking…</div>
                </div>
                <div style={{
                  padding: '12px 16px', background: 'var(--bg-card)',
                  border: '1px solid var(--border)', borderRadius: 10,
                }}>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                    {[0, 1, 2].map(n => (
                      <div
                        key={n}
                        style={{
                          width: 6, height: 6, borderRadius: '50%',
                          background: 'var(--accent)', opacity: 0.6,
                          animation: `pulse 1.2s ease-in-out ${n * 0.2}s infinite`,
                        }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Composer */}
        <div style={{ borderTop: '1px solid var(--border)', padding: 16, background: 'var(--bg-page)', flexShrink: 0 }}>
          <div style={{ maxWidth: 820, margin: '0 auto' }}>
            <div style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-strong)',
              borderRadius: 10, padding: 8,
            }}>
              <textarea
                ref={textareaRef}
                className="input"
                rows={2}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
                }}
                placeholder="Ask about an IOC, actor, CVE, or paste a threat brief to analyse…"
                style={{
                  height: 'auto', border: 'none', background: 'transparent',
                  padding: '6px 8px', resize: 'none', width: '100%',
                }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                {/* Attach + Tools buttons removed — they were stubs (no
                    file-upload backend, no per-call tool selection yet). */}
                <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--text-4)' }}>
                  ↵ to send · Shift+↵ for newline
                </span>
                <button
                  className="btn primary"
                  onClick={send}
                  disabled={loading || !input.trim()}
                >
                  {loading ? <Refresh s={11} /> : <Send s={11} />}
                  {loading ? 'Thinking…' : 'Send'}
                </button>
              </div>
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--text-mute)', textAlign: 'center', marginTop: 8 }}>
              Responses are grounded in your tenant&apos;s intel graph. Verify before acting.
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
