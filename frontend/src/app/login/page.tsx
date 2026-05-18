'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronRight } from '@/components/icons';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useStore((s) => s.setAuth);
  // Start empty so users type their own creds — no leaked default username.
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const tok = await api.post<{ access_token: string; refresh_token: string }>(
        '/login',
        { username, password },
      );
      setAuth(tok.access_token, { id: '', username, role: '', permissions: [] });
      try {
        const me = await api.get<{ id: string; username: string; role: string; permissions: string[] }>('/me');
        setAuth(tok.access_token, me);
      } catch {
        /* /me failed — keep the seeded user so we don't block login */
      }
      router.push('/');
    } catch {
      setError('Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  // Cyber dot positions for the background
  const dots = [
    [180, 140], [1260, 200], [1100, 720], [280, 760],
    [600, 80], [800, 820], [1340, 520], [120, 420],
  ];

  return (
    <div className="tip grid-bg" style={{ display: 'grid', placeItems: 'center' }}>
      {/* Scanning lines */}
      <div className="scan" style={{ animationDelay: '0s' }} />
      <div className="scan" style={{ animationDelay: '3s' }} />

      {/* Floating particle nodes (cyber dots) */}
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.5 }}>
        {dots.map((p, i) => (
          <g key={i}>
            <circle cx={p[0]} cy={p[1]} r={2} fill="#58a6ff" />
            <circle cx={p[0]} cy={p[1]} r={6} fill="none" stroke="#58a6ff" strokeOpacity="0.3" />
          </g>
        ))}
        <path d="M 180 140 L 600 80 L 1260 200" stroke="#58a6ff" strokeOpacity="0.18" fill="none" />
        <path d="M 280 760 L 800 820 L 1100 720 L 1340 520" stroke="#58a6ff" strokeOpacity="0.18" fill="none" />
      </svg>

      {/* Login card */}
      <div style={{ position: 'relative', zIndex: 2, display: 'grid', gridTemplateColumns: '1fr 380px', gap: 80, alignItems: 'center', width: 980, maxWidth: '95vw' }}>
        {/* Left — title only. Logo removed; tagline kept for character. */}
        <div>
          <div style={{ fontSize: 26, fontWeight: 600, color: '#fff', marginBottom: 24, letterSpacing: '-0.005em' }}>
            Cyber Threat Intelligence Platform
          </div>
          <div style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.15, color: 'var(--text)', maxWidth: 480, letterSpacing: '-0.015em' }}>
            See the adversary <span style={{ color: 'var(--accent)' }}>before</span> they see you.
          </div>
        </div>

        {/* Right — form. No SSO button, no version/build footer, no
            "corporate credentials" hint. Just the form. */}
        <form
          className="card"
          style={{ background: 'rgba(13,17,23,0.85)', backdropFilter: 'blur(8px)', padding: 28 }}
          onSubmit={handleLogin}
        >
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 22 }}>Sign in</div>

          {error && (
            <div style={{ fontSize: 12, color: 'var(--crit)', marginBottom: 12, padding: '6px 10px', background: 'var(--crit-bg)', borderRadius: 'var(--r-md)' }}>
              {error}
            </div>
          )}

          <label style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Username</label>
          <input
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ marginTop: 6, marginBottom: 14, height: 34 }}
            autoComplete="username"
            autoFocus
          />

          <label style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Password</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ marginTop: 6, marginBottom: 22, height: 34 }}
            autoComplete="current-password"
          />

          <button
            className="btn primary"
            type="submit"
            disabled={loading || !username || !password}
            style={{ width: '100%', height: 36, justifyContent: 'center', fontSize: 13 }}
          >
            {loading ? 'Signing in...' : <>Sign in <ChevronRight s={14} /></>}
          </button>
        </form>
      </div>
    </div>
  );
}
