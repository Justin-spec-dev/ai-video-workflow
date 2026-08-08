import type { ReactNode } from 'react';

/** Lightweight CSS-only tooltip wrapper (group-hover). */
export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1 -translate-x-1/2 whitespace-nowrap rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-[11px] text-zinc-200 opacity-0 shadow-lg transition-opacity group-hover:opacity-100"
      >
        {content}
      </span>
    </span>
  );
}
