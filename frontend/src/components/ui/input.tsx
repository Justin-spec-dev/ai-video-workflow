import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

const baseClasses =
  'w-full rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200 ' +
  'placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-600 ' +
  'disabled:cursor-not-allowed disabled:opacity-50';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(baseClasses, 'h-8', className)} {...props} />
  ),
);
Input.displayName = 'Input';

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn(baseClasses, 'min-h-[60px] resize-y', className)} {...props} />
  ),
);
Textarea.displayName = 'Textarea';
