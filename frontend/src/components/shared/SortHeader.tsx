'use client';

import React from 'react';
import { ChevronUp, ChevronDown } from '@/components/icons';

interface SortHeaderProps {
  label: string;
  sortKey: string;
  currentKey: string;
  currentDir: 'asc' | 'desc';
  onToggle: (key: string) => void;
  style?: React.CSSProperties;
}

export default function SortHeader({
  label, sortKey, currentKey, currentDir, onToggle, style,
}: SortHeaderProps) {
  const isActive = currentKey === sortKey;
  return (
    <th
      onClick={() => onToggle(sortKey)}
      style={{
        cursor: 'pointer',
        userSelect: 'none',
        ...style,
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
        {label}
        {isActive ? (
          currentDir === 'asc' ? <ChevronUp s={10} /> : <ChevronDown s={10} />
        ) : (
          <span style={{ opacity: 0.25, display: 'inline-flex' }}><ChevronDown s={10} /></span>
        )}
      </span>
    </th>
  );
}
