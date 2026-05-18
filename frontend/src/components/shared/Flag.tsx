'use client';

import React from 'react';

const FLAG_MAP: Record<string, string> = {
  CN: '\u{1F1E8}\u{1F1F3}', RU: '\u{1F1F7}\u{1F1FA}', IR: '\u{1F1EE}\u{1F1F7}',
  KP: '\u{1F1F0}\u{1F1F5}', US: '\u{1F1FA}\u{1F1F8}', MA: '\u{1F1F2}\u{1F1E6}',
  FR: '\u{1F1EB}\u{1F1F7}', DZ: '\u{1F1E9}\u{1F1FF}', TN: '\u{1F1F9}\u{1F1F3}',
  UA: '\u{1F1FA}\u{1F1E6}', BY: '\u{1F1E7}\u{1F1FE}', GB: '\u{1F1EC}\u{1F1E7}',
  DE: '\u{1F1E9}\u{1F1EA}', IL: '\u{1F1EE}\u{1F1F1}', BR: '\u{1F1E7}\u{1F1F7}',
  IN: '\u{1F1EE}\u{1F1F3}', VN: '\u{1F1FB}\u{1F1F3}', NG: '\u{1F1F3}\u{1F1EC}',
};

interface FlagProps {
  code: string;
}

export default function Flag({ code }: FlagProps) {
  // Only render for valid 2-letter country codes; skip author names, garbage, etc.
  if (!code || code.length !== 2 || !/^[A-Z]{2}$/.test(code)) return null;
  return (
    <span className="flag" title={code}>
      {FLAG_MAP[code] || code}
    </span>
  );
}
