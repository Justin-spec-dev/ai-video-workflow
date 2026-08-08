import { create } from 'zustand';
import { CheckCircle2, Info, XCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

export type ToastVariant = 'default' | 'success' | 'error';

export interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastStore {
  toasts: ToastItem[];
  push: (t: Omit<ToastItem, 'id'>) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: (t) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts.slice(-4), { ...t, id }] }));
    setTimeout(() => {
      useToastStore.getState().dismiss(id);
    }, 4500);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export function toast(title: string, opts?: { description?: string; variant?: ToastVariant }) {
  useToastStore.getState().push({ title, description: opts?.description, variant: opts?.variant ?? 'default' });
}

toast.success = (title: string, description?: string) => toast(title, { description, variant: 'success' });
toast.error = (title: string, description?: string) => toast(title, { description, variant: 'error' });

const icons: Record<ToastVariant, typeof Info> = {
  default: Info,
  success: CheckCircle2,
  error: XCircle,
};

const iconColors: Record<ToastVariant, string> = {
  default: 'text-sky-400',
  success: 'text-emerald-400',
  error: 'text-red-400',
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 flex-col gap-2">
      {toasts.map((t) => {
        const Icon = icons[t.variant];
        return (
          <div
            key={t.id}
            className={cn(
              'pointer-events-auto flex items-start gap-2 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 shadow-xl shadow-black/50',
            )}
            onClick={() => dismiss(t.id)}
          >
            <Icon size={15} className={cn('mt-0.5 shrink-0', iconColors[t.variant])} />
            <div className="min-w-0">
              <div className="text-xs font-medium text-zinc-100">{t.title}</div>
              {t.description ? (
                <div className="mt-0.5 break-words text-[11px] text-zinc-400">{t.description}</div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
