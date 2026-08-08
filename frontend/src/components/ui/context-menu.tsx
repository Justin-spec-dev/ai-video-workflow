import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface ContextMenuState {
  x: number;
  y: number;
}

/** Positioned context menu rendered at fixed (x, y); closes on outside click / Esc / item click. */
export function ContextMenu({
  state,
  onClose,
  children,
}: {
  state: ContextMenuState | null;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!state) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', onDown);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [state, onClose]);

  if (!state) return null;

  // Clamp inside viewport.
  const x = Math.min(state.x, window.innerWidth - 220);
  const y = Math.min(state.y, window.innerHeight - 320);

  return (
    <div
      ref={ref}
      style={{ left: x, top: y }}
      className="fixed z-50 min-w-[200px] rounded-md border border-zinc-700 bg-zinc-900 py-1 shadow-2xl shadow-black/60"
      onClick={onClose}
      onContextMenu={(e) => e.preventDefault()}
    >
      {children}
    </div>
  );
}

export function ContextMenuItem({
  children,
  onClick,
  disabled,
  danger,
  className,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  danger?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        if (!disabled) onClick?.();
      }}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-zinc-200 hover:bg-zinc-800',
        'disabled:cursor-not-allowed disabled:opacity-40',
        danger && 'text-red-300 hover:bg-red-950/50',
        className,
      )}
    >
      {children}
    </button>
  );
}

export function ContextMenuSeparator() {
  return <div className="my-1 h-px bg-zinc-800" />;
}
