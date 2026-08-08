import type { HTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

type BadgeVariant = 'default' | 'outline' | 'success' | 'warning' | 'danger' | 'muted';

const variants: Record<BadgeVariant, string> = {
  default: 'bg-zinc-700 text-zinc-100',
  outline: 'border border-zinc-600 text-zinc-300',
  success: 'bg-emerald-900/60 text-emerald-300',
  warning: 'bg-amber-900/60 text-amber-300',
  danger: 'bg-red-900/60 text-red-300',
  muted: 'bg-zinc-800 text-zinc-400',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
