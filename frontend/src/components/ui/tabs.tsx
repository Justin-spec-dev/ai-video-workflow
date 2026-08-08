import { createContext, useContext, type ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface TabsContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabs(): TabsContextValue {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error('Tabs components must be used inside <Tabs>');
  return ctx;
}

export interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
  children: ReactNode;
  className?: string;
}

export function Tabs({ value, onValueChange, children, className }: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={cn('flex min-h-0 flex-col', className)}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-center gap-1 border-b border-zinc-800 bg-zinc-900/60 px-2', className)}>
      {children}
    </div>
  );
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  const { value: current, onValueChange } = useTabs();
  const active = current === value;
  return (
    <button
      type="button"
      onClick={() => onValueChange(value)}
      className={cn(
        'border-b-2 px-3 py-1.5 text-xs font-medium transition-colors',
        active
          ? 'border-sky-500 text-zinc-100'
          : 'border-transparent text-zinc-400 hover:text-zinc-200',
      )}
    >
      {children}
    </button>
  );
}

export function TabsContent({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  const { value: current } = useTabs();
  if (current !== value) return null;
  return <div className={cn('min-h-0 flex-1 overflow-hidden', className)}>{children}</div>;
}
