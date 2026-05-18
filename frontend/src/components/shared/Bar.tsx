'use client';

import React from 'react';

interface BarProps {
  value: number;
  max?: number;
  variant?: string;
}

export default function Bar({ value, max = 1, variant }: BarProps) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className={`bar ${variant || ''}`} style={{ flex: 1, minWidth: 60 }}>
        <div className="fill" style={{ width: pct + '%' }} />
      </div>
      <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)', minWidth: 28, textAlign: 'right' }}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}
