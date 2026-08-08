import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

type Variant = 'default' | 'secondary' | 'ghost' | 'destructive' | 'outline' | 'success';
type Size = 'sm' | 'md' | 'xs' | 'icon';

const variantClasses: Record<Variant, string> = {
  default: 'bg-sky-600 text-white hover:bg-sky-500 disabled:bg-sky-900 disabled:text-zinc-400',
  secondary: 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 border border-zinc-700',
  ghost: 'text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100',
  destructive: 'bg-red-900/60 text-red-200 hover:bg-red-800/70 border border-red-900',
  outline: 'border border-zinc-700 text-zinc-200 hover:bg-zinc-800',
  success: 'bg-emerald-700 text-white hover:bg-emerald-600 disabled:bg-emerald-950 disabled:text-zinc-400',
};

const sizeClasses: Record<Size, string> = {
  xs: 'h-6 px-2 text-xs rounded',
  sm: 'h-7 px-2.5 text-xs rounded-md',
  md: 'h-8 px-3 text-sm rounded-md',
  icon: 'h-7 w-7 rounded-md',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500',
        'disabled:cursor-not-allowed disabled:opacity-60 select-none whitespace-nowrap',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = 'Button';
