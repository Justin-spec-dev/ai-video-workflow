import { forwardRef, type SelectHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

/** Styled native <select> — dense, dark, shadcn-flavoured. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'h-8 w-full rounded-md border border-zinc-700 bg-zinc-900 px-2 text-sm text-zinc-200',
        'focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-600',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = 'Select';
