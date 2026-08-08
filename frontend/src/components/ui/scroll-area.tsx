import type { HTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

/** Thin wrapper giving a consistently-styled scrollable region. */
export function ScrollArea({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('min-h-0 overflow-y-auto', className)} {...props} />;
}
