'use client';

import React from 'react';

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  fill?: boolean;
}

export default function Sparkline({ data, color = '#58a6ff', height = 28, fill = true }: SparklineProps) {
  const w = 100;
  const h = height;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    h - ((v - min) / range) * (h - 4) - 2,
  ]);
  const path = 'M ' + pts.map((p) => p.join(',')).join(' L ');
  const fillPath = path + ` L ${w},${h} L 0,${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height }}>
      {fill && <path d={fillPath} fill={color} fillOpacity="0.12" />}
      <path d={path} fill="none" stroke={color} strokeWidth="1.2" />
    </svg>
  );
}
