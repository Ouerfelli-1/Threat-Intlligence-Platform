'use client';

import React from 'react';

interface RingProps {
  value?: number;
  label?: string;
  sublabel?: string;
  size?: number;
  color?: string;
  track?: string;
  thickness?: number;
}

export default function Ring({
  value = 0.7,
  label,
  sublabel,
  size = 120,
  color = '#58a6ff',
  track = '#21262d',
  thickness = 8,
}: RingProps) {
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;

  return (
    <div className="ring-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={thickness} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeDasharray={`${c * value} ${c}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="vlabel">
        <div>
          <div
            style={{
              fontSize: size * 0.22,
              fontWeight: 600,
              color: 'var(--text)',
              letterSpacing: '-0.02em',
              lineHeight: 1,
              fontFeatureSettings: "'tnum'",
            }}
          >
            {label}
          </div>
          {sublabel && (
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-4)',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginTop: 3,
              }}
            >
              {sublabel}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
