// Connects /ws/events once per app lifetime and feeds events into runStore (§7).
import { useEffect } from 'react';
import { EventsSocket } from '../api/ws';
import { useRunStore } from '../stores/runStore';
import type { WSEvent } from '../types';

export function useWebsocket(): void {
  useEffect(() => {
    const socket = new EventsSocket();
    socket.onEvent = (event: WSEvent) => {
      useRunStore.getState().applyEvent(event);
    };
    socket.onStatus = (status) => {
      useRunStore.getState().setWsStatus(status);
    };
    socket.connect();
    return () => socket.disconnect();
  }, []);
}
