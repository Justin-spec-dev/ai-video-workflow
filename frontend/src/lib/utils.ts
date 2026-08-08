import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]): string {
  return clsx(...inputs);
}

export function shortId(id: string, head = 8): string {
  if (!id) return '';
  return id.length <= head ? id : `${id.slice(0, head)}…`;
}

export function newNodeId(type: string): string {
  return `${type}_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`;
}

export function formatTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export function formatClock(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}
