'use client';

import React from 'react';

interface StatusDotProps {
  status: string;
}

export default function StatusDot({ status }: StatusDotProps) {
  const cls =
    status === 'success' || status === 'ok' || status === 'completed'
      ? 'low'
      : status === 'running'
        ? 'med'
        : status === 'failed' || status === 'error'
          ? 'crit'
          : status === 'timeout' || status === 'pending'
            ? 'high'
            : 'mute';
  return <span className={`sev-dot ${cls}`} />;
}
