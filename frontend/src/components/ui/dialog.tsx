import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/** Minimal shadcn-style modal dialog (overlay + panel + esc/overlay close). */
export function Dialog({ open, onOpenChange, title, description, children, footer, className }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/70"
        onClick={() => onOpenChange(false)}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal
        className={cn(
          'relative z-10 flex max-h-[85vh] w-full max-w-lg flex-col rounded-lg border border-zinc-700',
          'bg-zinc-900 shadow-2xl shadow-black/60',
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-zinc-800 px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-zinc-100">{title}</h2>
            {description ? <p className="mt-0.5 text-xs text-zinc-400">{description}</p> : null}
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-2 border-t border-zinc-800 px-4 py-3">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}
