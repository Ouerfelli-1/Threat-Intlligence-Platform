// MERIDIAN — Lucide-style stroked SVG icons
// Each icon takes (size, color) implicitly via currentColor and CSS sizing on parent.
import React from 'react';

interface IconProps {
  d: React.ReactNode;
  s?: number;
  fill?: string;
  style?: React.CSSProperties;
  className?: string;
}

const Icon: React.FC<IconProps> = ({ d, s = 16, fill = 'none', style, className }) => (
  <svg viewBox="0 0 24 24" width={s} height={s} fill={fill} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" style={style} className={className}>
    {d}
  </svg>
);

interface IcoProps {
  s?: number;
  style?: React.CSSProperties;
  className?: string;
}

// Brand mark -- meridian: vertical line through a diamond
export function Mark({ s = 22 }: IcoProps) {
  return (
    <svg viewBox="0 0 24 24" width={s} height={s} fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M12 2L21 12L12 22L3 12Z" fill="rgba(88,166,255,0.08)" />
      <path d="M12 2V22" stroke="#58a6ff" />
      <path d="M3 12H21" stroke="#58a6ff" strokeOpacity="0.45" />
      <circle cx="12" cy="12" r="2.2" fill="#58a6ff" stroke="none" />
    </svg>
  );
}

export function Home(p: IcoProps) { return <Icon {...p} d={<><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /></>} />; }
export function Compass(p: IcoProps) { return <Icon {...p} d={<><circle cx="12" cy="12" r="9" /><path d="M15 9l-2 6-6 2 2-6 6-2z" /></>} />; }
export function Bug(p: IcoProps) { return <Icon {...p} d={<><rect x="8" y="6" width="8" height="14" rx="4" /><path d="M12 6V3M9 4l-2-1M15 4l2-1M5 12H3M5 16H3M19 12h2M19 16h2" /></>} />; }
export function AlertTriangle(p: IcoProps) { return <Icon {...p} d={<><path d="M12 2L22 20H2L12 2z" /><path d="M12 9v5M12 17h0" /></>} />; }
export function Crosshair(p: IcoProps) { return <Icon {...p} d={<><circle cx="12" cy="12" r="9" /><path d="M12 3v4M12 17v4M3 12h4M17 12h4" /></>} />; }
export function Search(p: IcoProps) { return <Icon {...p} d={<><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>} />; }
export function Scope(p: IcoProps) { return <Icon {...p} d={<><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3" /></>} />; }
export function Users(p: IcoProps) { return <Icon {...p} d={<><circle cx="9" cy="8" r="4" /><path d="M2 21c0-3.9 3.1-7 7-7s7 3.1 7 7" /><circle cx="17" cy="6" r="3" /><path d="M22 16c0-2.2-1.8-4-4-4" /></>} />; }
export function Skull(p: IcoProps) { return <Icon {...p} d={<><path d="M5 12a7 7 0 0 1 14 0v3l-2 2v3H7v-3l-2-2v-3z" /><circle cx="9" cy="11" r="1" /><circle cx="15" cy="11" r="1" /></>} />; }
export function Plug(p: IcoProps) { return <Icon {...p} d={<><path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8zM12 17v5" /></>} />; }
export function Shield(p: IcoProps) { return <Icon {...p} d={<><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" /></>} />; }
export function Server(p: IcoProps) { return <Icon {...p} d={<><rect x="3" y="4" width="18" height="7" rx="1.5" /><rect x="3" y="13" width="18" height="7" rx="1.5" /><path d="M7 7.5h.01M7 16.5h.01" /></>} />; }
export function Building(p: IcoProps) { return <Icon {...p} d={<><rect x="4" y="3" width="16" height="18" rx="1" /><path d="M9 8h.01M15 8h.01M9 12h.01M15 12h.01M9 16h.01M15 16h.01" /></>} />; }
export function Globe(p: IcoProps) { return <Icon {...p} d={<><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>} />; }
export function Radar(p: IcoProps) { return <Icon {...p} d={<><path d="M19.07 4.93A10 10 0 1 1 12 2v4" /><path d="M12 12L8 8" /><circle cx="12" cy="12" r="1" /></>} />; }
export function Calendar(p: IcoProps) { return <Icon {...p} d={<><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" /></>} />; }
export function Gauge(p: IcoProps) { return <Icon {...p} d={<><path d="M12 14L17 8M22 14a10 10 0 1 0-20 0" /></>} />; }
export function FileText(p: IcoProps) { return <Icon {...p} d={<><path d="M14 2H6v20h12V8z" /><path d="M14 2v6h6M8 13h8M8 17h6" /></>} />; }
export function Sparkles(p: IcoProps) { return <Icon {...p} d={<><path d="M12 2l1.7 5.3L19 9l-5.3 1.7L12 16l-1.7-5.3L5 9l5.3-1.7z" /><path d="M19 16l.7 2L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-1z" /></>} />; }
export function MessageSquare(p: IcoProps) { return <Icon {...p} d={<><path d="M21 12a8 8 0 0 1-8 8H4l3-3v-5a8 8 0 0 1 8-8 8 8 0 0 1 6 3" /></>} />; }
export function Settings(p: IcoProps) { return <Icon {...p} d={<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>} />; }
export function Bell(p: IcoProps) { return <Icon {...p} d={<><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" /></>} />; }
export function ChevronUp(p: IcoProps) { return <Icon {...p} d={<path d="M6 15l6-6 6 6" />} />; }
export function ChevronDown(p: IcoProps) { return <Icon {...p} d={<path d="M6 9l6 6 6-6" />} />; }
export function ChevronRight(p: IcoProps) { return <Icon {...p} d={<path d="M9 6l6 6-6 6" />} />; }
export function ChevronLeft(p: IcoProps) { return <Icon {...p} d={<path d="M15 6l-6 6 6 6" />} />; }
export function Plus(p: IcoProps) { return <Icon {...p} d={<path d="M12 5v14M5 12h14" />} />; }
export function Trash(p: IcoProps) { return <Icon {...p} d={<><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6M10 11v6M14 11v6M9 6V4h6v2" /></>} />; }
export function More(p: IcoProps) { return <Icon {...p} d={<><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>} />; }
export function Filter(p: IcoProps) { return <Icon {...p} d={<path d="M3 4h18l-7 9v6l-4-2v-4z" />} />; }
export function Download(p: IcoProps) { return <Icon {...p} d={<><path d="M12 4v12M6 12l6 6 6-6M4 20h16" /></>} />; }
export function Upload(p: IcoProps) { return <Icon {...p} d={<><path d="M12 20V8M6 12l6-6 6 6M4 4h16" /></>} />; }
export function Refresh(p: IcoProps) { return <Icon {...p} d={<><path d="M3 12a9 9 0 0 1 15.5-6.5L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.5L3 16M3 21v-5h5" /></>} />; }
export function Play(p: IcoProps) { return <Icon {...p} d={<path d="M6 4l14 8-14 8z" />} />; }
export function Pause(p: IcoProps) { return <Icon {...p} d={<><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></>} />; }
export function Check(p: IcoProps) { return <Icon {...p} d={<path d="M5 12l5 5L20 7" />} />; }
export function X(p: IcoProps) { return <Icon {...p} d={<path d="M6 6l12 12M18 6L6 18" />} />; }
export function Link(p: IcoProps) { return <Icon {...p} d={<><path d="M10 14a5 5 0 0 1 0-7l3-3a5 5 0 0 1 7 7l-2 2" /><path d="M14 10a5 5 0 0 1 0 7l-3 3a5 5 0 0 1-7-7l2-2" /></>} />; }
export function Clock(p: IcoProps) { return <Icon {...p} d={<><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>} />; }
export function Pin(p: IcoProps) { return <Icon {...p} d={<><path d="M15 2l7 7-5 1-4 4 1 5-4-4L4 20l4-6-4-4 5 1 4-4z" /></>} />; }
export function Layers(p: IcoProps) { return <Icon {...p} d={<><path d="M12 3l9 5-9 5-9-5z" /><path d="M3 13l9 5 9-5M3 18l9 5 9-5" /></>} />; }
export function GitBranch(p: IcoProps) { return <Icon {...p} d={<><circle cx="6" cy="5" r="2" /><circle cx="6" cy="19" r="2" /><circle cx="18" cy="12" r="2" /><path d="M6 7v10M16 12H8c-1.1 0-2-.9-2-2" /></>} />; }
export function Eye(p: IcoProps) { return <Icon {...p} d={<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" /><circle cx="12" cy="12" r="3" /></>} />; }
export function Cmd(p: IcoProps) { return <Icon {...p} d={<><rect x="3" y="3" width="6" height="6" rx="3" /><rect x="15" y="3" width="6" height="6" rx="3" /><rect x="3" y="15" width="6" height="6" rx="3" /><rect x="15" y="15" width="6" height="6" rx="3" /><path d="M9 6h6M9 18h6M6 9v6M18 9v6" /></>} />; }
export function Brain(p: IcoProps) { return <Icon {...p} d={<><path d="M9 3a3 3 0 0 1 3 3v12a3 3 0 0 1-6 0 3 3 0 0 1-3-3 3 3 0 0 1 1-2 3 3 0 0 1-1-2 3 3 0 0 1 3-3 3 3 0 0 1 3-3z" /><path d="M15 3a3 3 0 0 0-3 3v12a3 3 0 0 0 6 0 3 3 0 0 0 3-3 3 3 0 0 0-1-2 3 3 0 0 0 1-2 3 3 0 0 0-3-3 3 3 0 0 0-3-3z" /></>} />; }
export function Paperclip(p: IcoProps) { return <Icon {...p} d={<path d="M21 12L12 21a5.5 5.5 0 0 1-8-8l9-9a4 4 0 0 1 5.5 5.5l-9 9a2 2 0 0 1-3-3l8-8" />} />; }
export function Activity(p: IcoProps) { return <Icon {...p} d={<path d="M22 12h-4l-3 9-6-18-3 9H2" />} />; }
export function Lock(p: IcoProps) { return <Icon {...p} d={<><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>} />; }
export function Send(p: IcoProps) { return <Icon {...p} d={<><path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4z" /></>} />; }
export function Camera(p: IcoProps) { return <Icon {...p} d={<><path d="M2 7h4l2-3h8l2 3h4v13H2z" /><circle cx="12" cy="13" r="4" /></>} />; }
export function ExternalLink(p: IcoProps) { return <Icon {...p} d={<><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></>} />; }
export function Package(p: IcoProps) { return <Icon {...p} d={<><path d="M16.5 9.4l-9-5.19M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></>} />; }
export function Network(p: IcoProps) { return <Icon {...p} d={<><circle cx="12" cy="5" r="2" /><circle cx="5" cy="19" r="2" /><circle cx="19" cy="19" r="2" /><path d="M12 7v4M12 11l-5 6M12 11l5 6" /></>} />; }

// Icon lookup map for dynamic resolution
export const I: Record<string, React.FC<IcoProps>> = {
  Mark, Home, Compass, Bug, AlertTriangle, Crosshair, Search, Scope,
  Users, Skull, Plug, Shield, Server, Building, Globe, Radar, Calendar,
  Gauge, FileText, Sparkles, MessageSquare, Settings, Bell,
  ChevronDown, ChevronRight, ChevronLeft, Plus, More, Filter,
  Download, Upload, Refresh, Play, Pause, Check, X, Link, Clock,
  Pin, Layers, GitBranch, Eye, Cmd, Brain, Paperclip, Activity,
  Lock, Send, Camera, Trash, ExternalLink, Package, Network,
};
