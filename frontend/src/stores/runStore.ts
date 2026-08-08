// runStore (SPEC §10): current run, node statuses, logs, tasks, runs — driven by WS events (§7).
import { create } from 'zustand';
import type { WSStatus } from '../api/ws';
import type {
  CostEstimate,
  LogEntry,
  NodeOutputs,
  NodeStatus,
  ProviderTask,
  RunDetail,
  RunStatus,
  TaskEventPayload,
  WorkflowRun,
} from '../types';

const LOG_LIMIT = 2000;

export interface NodeStatusInfo {
  status: NodeStatus;
  error?: string;
}

const NODE_EVENT_STATUS: Record<string, NodeStatus> = {
  'node.queued': 'QUEUED',
  'node.running': 'RUNNING',
  'node.waiting_confirmation': 'WAITING_CONFIRMATION',
  'node.success': 'SUCCESS',
  'node.failed': 'FAILED',
  'node.cached': 'CACHED',
  'node.cancelled': 'CANCELLED',
};

const TASK_EVENT_STATUS: Record<string, string> = {
  'task.created': 'queued',
  'task.processing': 'running',
  'task.success': 'succeeded',
  'task.failed': 'failed',
};

interface RunStoreState {
  currentRunId: string | null;
  currentRunStatus: RunStatus | null;
  nodeStatuses: Record<string, NodeStatusInfo>;
  nodeOutputs: Record<string, NodeOutputs>;
  logs: LogEntry[];
  tasks: ProviderTask[];
  runs: WorkflowRun[];
  estimate: CostEstimate | null;
  wsStatus: WSStatus;

  applyEvent: (event: { event: string; ts: number; payload: Record<string, unknown> }) => void;
  /** 打开工作流时用最近一次运行的 node_runs 回填节点状态与输出（预览图/视频立即可见）。 */
  hydrateFromRun: (run: RunDetail) => void;
  setNodeStatus: (nodeId: string, status: NodeStatus, error?: string) => void;
  resetRun: () => void;
  addLog: (entry: LogEntry) => void;
  setTasks: (tasks: ProviderTask[]) => void;
  upsertTask: (task: ProviderTask) => void;
  setRuns: (runs: WorkflowRun[]) => void;
  setEstimate: (estimate: CostEstimate | null) => void;
  setWsStatus: (status: WSStatus) => void;
}

export const useRunStore = create<RunStoreState>((set, get) => ({
  currentRunId: null,
  currentRunStatus: null,
  nodeStatuses: {},
  nodeOutputs: {},
  logs: [],
  tasks: [],
  runs: [],
  estimate: null,
  wsStatus: 'closed',

  applyEvent: (raw) => {
    const { event, ts, payload } = raw as { event: string; ts: number; payload: Record<string, unknown> };

    if (event === 'workflow.started') {
      set({
        currentRunId: (payload.run_id as string) ?? null,
        currentRunStatus: 'running',
        nodeStatuses: {},
        nodeOutputs: {},
        logs: [],
      });
      return;
    }

    if (event in NODE_EVENT_STATUS) {
      const nodeId = payload.node_id as string | undefined;
      if (!nodeId) return;
      const status = NODE_EVENT_STATUS[event];
      set({
        nodeStatuses: { ...get().nodeStatuses, [nodeId]: { status, error: payload.error as string | undefined } },
      });
      if (status === 'SUCCESS' || status === 'CACHED') {
        const outputs = payload.outputs as NodeOutputs | undefined;
        if (outputs) set({ nodeOutputs: { ...get().nodeOutputs, [nodeId]: outputs } });
      }
      return;
    }

    if (event in TASK_EVENT_STATUS) {
      const p = payload as unknown as TaskEventPayload;
      if (!p.task_id) return;
      const existing = get().tasks.find((t) => t.id === p.task_id);
      const merged: ProviderTask = {
        id: p.task_id,
        run_id: (p.run_id as string) ?? existing?.run_id ?? get().currentRunId ?? '',
        workflow_id: existing?.workflow_id ?? '',
        node_id: p.node_id ?? existing?.node_id ?? '',
        provider: (p.provider as string) ?? existing?.provider ?? '',
        model: (p.model as string | null) ?? existing?.model ?? null,
        remote_task_id: (p.remote_task_id as string | null) ?? existing?.remote_task_id ?? null,
        status: TASK_EVENT_STATUS[event],
        remote_status: p.remote_status ?? existing?.remote_status ?? null,
        output: (p.output as ProviderTask['output']) ?? existing?.output ?? null,
        error: (p.error as string | null) ?? existing?.error ?? null,
        created_at: existing?.created_at,
        started_at: existing?.started_at,
        finished_at: existing?.finished_at,
      };
      get().upsertTask(merged);
      return;
    }

    if (event === 'log') {
      get().addLog({
        ts: ts * 1000,
        run_id: payload.run_id as string | undefined,
        node_id: payload.node_id as string | undefined,
        level: (payload.level as string) ?? 'info',
        message: (payload.message as string) ?? '',
      });
      return;
    }

    if (event === 'workflow.finished') {
      set({ currentRunStatus: (payload.status as RunStatus) ?? null });
      return;
    }

    if (event === 'workflow.cost') {
      const estimate = payload.estimate as CostEstimate | undefined;
      if (estimate) set({ estimate });
      return;
    }
  },

  setNodeStatus: (nodeId, status, error) => {
    set({ nodeStatuses: { ...get().nodeStatuses, [nodeId]: { status, error } } });
  },

  hydrateFromRun: (run) => {
    const nodeStatuses: Record<string, NodeStatusInfo> = {};
    const nodeOutputs: Record<string, NodeOutputs> = {};
    for (const nr of run.node_runs ?? []) {
      if (!nr.node_id || !nr.status) continue;
      nodeStatuses[nr.node_id] = { status: nr.status, error: nr.error ?? undefined };
      // 后端有时返回 JSON 字符串，有时返回已解析对象——两种都兼容
      let outs: unknown = nr.outputs;
      if (typeof outs === 'string') {
        try {
          outs = JSON.parse(outs);
        } catch {
          outs = null;
        }
      }
      if (outs && typeof outs === 'object' && (nr.status === 'SUCCESS' || nr.status === 'CACHED')) {
        nodeOutputs[nr.node_id] = outs as NodeOutputs;
      }
    }
    set({
      currentRunId: run.id ?? null,
      currentRunStatus: run.status ?? null,
      nodeStatuses,
      nodeOutputs,
    });
  },

  resetRun: () => {
    set({
      currentRunId: null,
      currentRunStatus: null,
      nodeStatuses: {},
      nodeOutputs: {},
      logs: [],
      tasks: [],
      estimate: null,
    });
  },

  addLog: (entry) => {
    set({ logs: [...get().logs.slice(-(LOG_LIMIT - 1)), entry] });
  },

  setTasks: (tasks) => set({ tasks }),

  upsertTask: (task) => {
    const tasks = get().tasks;
    const idx = tasks.findIndex((t) => t.id === task.id);
    if (idx === -1) set({ tasks: [...tasks, task] });
    else set({ tasks: tasks.map((t, i) => (i === idx ? { ...t, ...task } : t)) });
  },

  setRuns: (runs) => set({ runs }),
  setEstimate: (estimate) => set({ estimate }),
  setWsStatus: (wsStatus) => set({ wsStatus }),
}));
