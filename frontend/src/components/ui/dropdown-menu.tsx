import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface DropdownMenuProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: 'left' | 'right';
  triggerClassName?: string;
  showCaret?: boolean;
}

/** Minimal dropdown menu: click trigger to open, outside-click / Esc to close. */
export function DropdownMenu({ trigger, children, align = 'left', triggerClassName, showCaret = true }: DropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900 px-2.5 text-sm text-zinc-200 hover:bg-zinc-800',
          triggerClassName,
        )}
      >
        {trigger}
        {showCaret ? <ChevronDown size={13} className="text-zinc-500" /> : null}
      </button>
      {open ? (
        <div
          className={cn(
            'absolute z-40 mt-1 max-h-80 min-w-[220px] overflow-y-auto rounded-md border border-zinc-700 bg-zinc-900 py-1 shadow-xl shadow-black/50',
            align === 'right' ? 'right-0' : 'left-0',
          )}
          // Close after any item click.
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function DropdownItem({
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

export function DropdownLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
      {children}
    </div>
  );
}

export function DropdownSeparator() {
  return <div className="my-1 h-px bg-zinc-800" />;
}
