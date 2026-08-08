// Global keyboard shortcuts (SPEC §10):
// Delete · Ctrl+C/V · Ctrl+Z / Ctrl+Shift+Z · Ctrl+S · Space opens node search.
import { useReactFlow } from '@xyflow/react';
import { useEffect } from 'react';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

/** Must be called from inside a ReactFlowProvider (uses useReactFlow). */
export function useShortcuts(): void {
  const { screenToFlowPosition } = useReactFlow();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const wf = useWorkflowStore.getState();
      const ui = useUIStore.getState();
      const typing = isTypingTarget(e.target);

      if (e.ctrlKey || e.metaKey) {
        const key = e.key.toLowerCase();
        if (key === 's') {
          e.preventDefault();
          void wf.saveWorkflow();
        } else if (!typing && key === 'c') {
          wf.copySelection();
        } else if (!typing && key === 'v') {
          wf.paste();
        } else if (!typing && key === 'z') {
          e.preventDefault();
          if (e.shiftKey) wf.redo();
          else wf.undo();
        }
        return;
      }

      if (typing) return;

      if (e.key === 'Delete' || e.key === 'Backspace') {
        wf.deleteSelection();
      } else if (e.key === ' ') {
        // Space opens the node search palette (unless a dialog is already up).
        if (ui.nodeSearch.open || ui.credentialsOpen || ui.estimateOpen || ui.inspect) return;
        e.preventDefault();
        const center = screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
        ui.openNodeSearch(center.x, center.y);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [screenToFlowPosition]);
}
