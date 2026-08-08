import { ReactFlowProvider } from '@xyflow/react';
import { useEffect, useRef, useState } from 'react';
import * as api from './api/resources';
import { BottomPanel } from './components/BottomPanel';
import { CredentialsDialog } from './components/CredentialsDialog';
import { EstimateDialog } from './components/EstimateDialog';
import { InspectDialog } from './components/InspectDialog';
import { NodeLibrary } from './components/NodeLibrary';
import { PropertiesPanel } from './components/PropertiesPanel';
import { QuickStartDialog } from './components/QuickStartDialog';
import { TopBar } from './components/TopBar';
import { Toaster } from './components/ui/toast';
import { useWebsocket } from './hooks/useWebsocket';
import { useCredentialStore } from './stores/credentialStore';
import { getLastWorkflowId, useWorkflowStore } from './stores/workflowStore';
import { Canvas } from './workflow/Canvas';

function useBootstrap(): { ready: boolean; error: string | null } {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // StrictMode double-invoke guard
    started.current = true;

    /** 后端可能正在重启：短暂退避重试，避免把瞬断误判为"没有工作流"。 */
    const withRetry = async <T,>(fn: () => Promise<T>, attempts = 4): Promise<T> => {
      let lastErr: unknown;
      for (let i = 0; i < attempts; i++) {
        try {
          return await fn();
        } catch (e) {
          lastErr = e;
          await new Promise((r) => setTimeout(r, 800 * 2 ** i));
        }
      }
      throw lastErr;
    };

    const boot = async () => {
      const wf = useWorkflowStore.getState();

      try {
        // 1) Node schemas drive everything downstream.
        const { data: schemas } = await withRetry(() => api.getNodes());
        wf.setSchemas(schemas);

        // 2) Credentials + providers (for credential dropdowns).
        void useCredentialStore.getState().loadAll();

        // 3) Restore the last opened workflow (localStorage holds ONLY the id, §10).
        const { data: list } = await withRetry(() => api.listWorkflows());
        const lastId = getLastWorkflowId();
        const target = list.find((w) => w.id === lastId) ?? list[0];
        if (target) {
          const { data: record } = await api.getWorkflow(target.id);
          wf.loadWorkflow(record);
        } else {
          // 只有确认后端正常且确实没有任何工作流时才新建
          await wf.newWorkflow();
        }
        setReady(true);
      } catch (e) {
        // 静默白屏是工作流"丢失"误解的根源：明确报错并给重试入口
        setError(e instanceof Error ? e.message : '无法连接后端');
      }
    };

    void boot();
  }, []);

  return { ready, error };
}

export default function App() {
  useWebsocket();
  const { ready, error } = useBootstrap();

  return (
    <div className="flex h-full flex-col bg-zinc-950 text-zinc-200">
      <TopBar />
      {ready ? (
        <div className="flex min-h-0 flex-1">
          <NodeLibrary />
          <div className="flex min-w-0 flex-1 flex-col">
            <ReactFlowProvider>
              <Canvas />
            </ReactFlowProvider>
            <BottomPanel />
          </div>
          <PropertiesPanel />
        </div>
      ) : error ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-sm">
          <p className="text-red-400">工作区加载失败：{error}</p>
          <p className="text-xs text-zinc-500">请确认后端已启动（:8000）。你的工作流数据不会丢失。</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-md border border-zinc-700 px-4 py-1.5 text-xs text-zinc-200 hover:bg-zinc-800"
          >
            重新加载
          </button>
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
          正在加载工作区…
        </div>
      )}

      <CredentialsDialog />
      <EstimateDialog />
      <InspectDialog />
      <QuickStartDialog />
      <Toaster />
    </div>
  );
}
