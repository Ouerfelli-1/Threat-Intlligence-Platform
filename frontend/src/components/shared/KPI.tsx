'use client';

import React from 'react';
import Sparkline from './Sparkline';

interface KPIProps {
  label: string;
  value: string;
  delta?: string;
  deltaDir?: 'up' | 'dn';
  spark?: number[];
  color?: string;
  live?: boolean;
}

export default function KPI({ label, value, delta, deltaDir = 'up', spark, color = '#58a6ff', live }: KPIProps) {
  return (
    <div className="card kpi" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="label">{label}</div>
        {live && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--low)' }}>
            <span className="sev-dot low pulse" />LIVE
          </div>
        )}
      </div>
      <div className="v">{value}</div>
      {delta && <div className={`d ${deltaDir}`}>{delta}</div>}
      {spark && (
        <div className="spark">
          <Sparkline data={spark} color={color} />
        </div>
      )}
    </div>
  );
}
