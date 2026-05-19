import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
// ReactFlow ships its own stylesheet (handles, controls, minimap, edges).
// Imported globally so any page that mounts <AttackFlowGraph> picks it up
// without each page having to remember.
import 'reactflow/dist/style.css';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  variable: '--font-jetbrains',
  subsets: ['latin'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Cyber Threat Intelligence Platform',
  description: 'Cyber Threat Intelligence Platform',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} style={{ height: '100%' }}>
      <body style={{ margin: 0, height: '100%' }}>{children}</body>
    </html>
  );
}
