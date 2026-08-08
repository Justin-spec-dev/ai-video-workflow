// WebSocket client for /ws/events (SPEC §7) with exponential backoff reconnect (max 10 attempts).
import type { WSEvent } from '../types';

export type WSStatus = 'connecting' | 'open' | 'closed';

const MAX_RETRIES = 10;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export class EventsSocket {
  private ws: WebSocket | null = null;
  private retries = 0;
  private stopped = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  onEvent: (event: WSEvent) => void = () => {};
  onStatus: (status: WSStatus) => void = () => {};

  private url(): string {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws/events`;
  }

  connect(): void {
    if (this.ws || this.stopped) return;
    this.onStatus('connecting');
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url());
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.retries = 0;
      this.onStatus('open');
    };
    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data as string) as WSEvent;
        this.onEvent(event);
      } catch {
        // Ignore malformed frames.
      }
    };
    ws.onclose = () => {
      this.ws = null;
      this.onStatus('closed');
      this.scheduleReconnect();
    };
    ws.onerror = () => {
      // onclose follows and handles reconnect.
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.retries >= MAX_RETRIES) return;
    const delay = Math.min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** this.retries);
    this.retries += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  disconnect(): void {
    this.stopped = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      try {
        ws.close();
      } catch {
        /* noop */
      }
    }
    this.onStatus('closed');
  }
}
