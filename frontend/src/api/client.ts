// Typed fetch wrapper for the /api REST contract (SPEC §6).
// Unified error shape: {"detail": "..."} + HTTP status.

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiResult<T> {
  status: number;
  data: T;
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === 'string') return d;
    return JSON.stringify(d);
  }
  if (typeof body === 'string' && body) return body;
  return fallback;
}

async function request<T>(
  method: string,
  url: string,
  body?: unknown,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...init,
    });
  } catch (e) {
    throw new ApiError(0, e instanceof Error ? e.message : 'Network error');
  }
  const parsed = await parseBody(res);
  if (!res.ok) {
    throw new ApiError(res.status, extractDetail(parsed, `HTTP ${res.status}`));
  }
  return { status: res.status, data: parsed as T };
}

export const http = {
  get: <T>(url: string) => request<T>('GET', url),
  post: <T>(url: string, body?: unknown) => request<T>('POST', url, body),
  put: <T>(url: string, body?: unknown) => request<T>('PUT', url, body),
  delete: <T>(url: string) => request<T>('DELETE', url),

  async upload<T>(url: string, file: File): Promise<ApiResult<T>> {
    const form = new FormData();
    form.append('file', file);
    let res: Response;
    try {
      res = await fetch(url, { method: 'POST', body: form });
    } catch (e) {
      throw new ApiError(0, e instanceof Error ? e.message : 'Network error');
    }
    const parsed = await parseBody(res);
    if (!res.ok) {
      throw new ApiError(res.status, extractDetail(parsed, `HTTP ${res.status}`));
    }
    return { status: res.status, data: parsed as T };
  },
};
