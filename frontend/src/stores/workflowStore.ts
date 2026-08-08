// workflowStore (SPEC §10): React Flow nodes/edges + workflow identity + dirty/autosave
// + undo/redo snapshot stack (max 50, structural changes only) + clipboard.
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type NodeChange,
} from '@xyflow/react';
import { create } from 'zustand';
import * as api from '../api/resources';
import { toast } from '../components/ui/toast';
import { newNodeId } from '../lib/utils';
import type { NodeSchema, NodeStatus, Viewport, WorkflowJSON, WorkflowRecord } from '../types';
import type { SchemaFlowNode } from '../types/rf';
import { validateConnection } from '../workflow/validation';
import { useRunStore } from './runStore';

const LS_LAST_WORKFLOW = 'aivwf.last_workflow_id';
const AUTOSAVE_MS = 1500;
const UNDO_LIMIT = 50;
const PASTE_OFFSET = 32;

export function getLastWorkflowId(): string | null {
  return localStorage.getItem(LS_LAST_WORKFLOW);
}

function setLastWorkflowId(id: string): void {
  // Only the workflow id may be persisted — never keys/secrets (SPEC §10).
  localStorage.setItem(LS_LAST_WORKFLOW, id);
}

interface Snapshot {
  nodes: SchemaFlowNode[];
  edges: Edge[];
}

export type SaveState = 'saved' | 'saving' | 'dirty' | 'error';

interface WorkflowStoreState {
  workflowId: string | null;
  workflowName: string;
  nodes: SchemaFlowNode[];
  edges: Edge[];
  viewport: Viewport;
  dirty: boolean;
  saveState: SaveState;
  nodeSchemas: Record<string, NodeSchema>;
  schemasLoaded: boolean;
  past: Snapshot[];
  future: Snapshot[];
  clipboard: Snapshot | null;

  setSchemas: (schemas: NodeSchema[]) => void;
  onNodesChange: (changes: NodeChange<SchemaFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<Edge>[]) => void;
  onConnect: (conn: Connection) => void;
  isValidConnection: (conn: Connection | Edge) => boolean;
  addNode: (nodeType: string, position: { x: number; y: number }) => void;
  deleteSelection: () => void;
  copySelection: () => void;
  paste: () => void;
  undo: () => void;
  redo: () => void;
  updateNodeConfigValue: (nodeId: string, key: string, value: unknown) => void;
  setNodeConfig: (nodeId: string, config: Record<string, unknown>) => void;
  setWorkflowName: (name: string) => void;
  setViewport: (viewport: Viewport) => void;
  serialize: () => WorkflowJSON;
  loadWorkflow: (record: WorkflowRecord) => void;
  newWorkflow: () => Promise<void>;
  saveWorkflow: () => Promise<void>;
  markDirty: () => void;
  applyNodeStatus: (nodeId: string, status: NodeStatus, error?: string) => void;
  resetStatuses: () => void;
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;

function newEdgeId(): string {
  return `e_${crypto.randomUUID().replace(/-/g, '').slice(0, 10)}`;
}

export const useWorkflowStore = create<WorkflowStoreState>((set, get) => {
  /** Push an undo snapshot before a structural (nodes/edges) mutation. */
  const pushSnapshot = () => {
    const { nodes, edges, past } = get();
    const next = [...past, { nodes, edges }].slice(-UNDO_LIMIT);
    set({ past: next, future: [] });
  };

  const markDirty = () => {
    set({ dirty: true, saveState: 'dirty' });
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      void get().saveWorkflow();
    }, AUTOSAVE_MS);
  };

  return {
    workflowId: null,
    workflowName: '未命名工作流',
    nodes: [],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
    dirty: false,
    saveState: 'saved',
    nodeSchemas: {},
    schemasLoaded: false,
    past: [],
    future: [],
    clipboard: null,

    setSchemas: (schemas) => {
      const map: Record<string, NodeSchema> = {};
      for (const s of schemas) map[s.type] = s;
      set({ nodeSchemas: map, schemasLoaded: true });
    },

    onNodesChange: (changes) => {
      const structural = changes.some((c) => c.type === 'remove' || c.type === 'add');
      if (structural) pushSnapshot();
      const nodes = applyNodeChanges<SchemaFlowNode>(changes, get().nodes);
      set({ nodes });
      if (changes.some((c) => c.type === 'remove' || c.type === 'add' || c.type === 'position')) {
        markDirty();
      }
    },

    onEdgesChange: (changes) => {
      const structural = changes.some((c) => c.type === 'remove' || c.type === 'add');
      if (structural) pushSnapshot();
      const edges = applyEdgeChanges<Edge>(changes, get().edges);
      set({ edges });
      if (structural) markDirty();
    },

    isValidConnection: (conn) => {
      const { nodes, edges, nodeSchemas } = get();
      return validateConnection(conn, nodes, edges, nodeSchemas).ok;
    },

    onConnect: (conn) => {
      const { nodes, edges, nodeSchemas } = get();
      const check = validateConnection(conn, nodes, edges, nodeSchemas);
      if (!check.ok) {
        toast.error('连接被拒绝', check.reason);
        return;
      }
      pushSnapshot();
      const next = addEdge<Edge>({ ...conn, id: newEdgeId() }, edges);
      set({ edges: next });
      markDirty();
    },

    addNode: (nodeType, position) => {
      const schema = get().nodeSchemas[nodeType];
      if (!schema) {
        toast.error('未知节点类型', nodeType);
        return;
      }
      const config: Record<string, unknown> = {};
      for (const field of schema.config_schema) {
        if (field.default !== undefined && field.default !== null) config[field.key] = field.default;
      }
      pushSnapshot();
      const node: SchemaFlowNode = {
        id: newNodeId(nodeType),
        type: 'schemaNode',
        position,
        data: { nodeType, config },
        selected: true,
      };
      set({ nodes: [...get().nodes.map((n) => ({ ...n, selected: false })), node] });
      markDirty();
    },

    deleteSelection: () => {
      const { nodes, edges } = get();
      const removed = new Set(nodes.filter((n) => n.selected).map((n) => n.id));
      const hasEdgeRemoval = edges.some((e) => e.selected);
      if (removed.size === 0 && !hasEdgeRemoval) return;
      pushSnapshot();
      const nextNodes = nodes.filter((n) => !n.selected);
      const nextEdges = edges.filter(
        (e) => !e.selected && !removed.has(e.source) && !removed.has(e.target),
      );
      set({ nodes: nextNodes, edges: nextEdges });
      markDirty();
    },

    copySelection: () => {
      const { nodes, edges } = get();
      const selectedNodes = nodes.filter((n) => n.selected);
      if (selectedNodes.length === 0) return;
      const ids = new Set(selectedNodes.map((n) => n.id));
      const selectedEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
      set({
        clipboard: {
          nodes: selectedNodes.map((n) => ({ ...n, data: { ...n.data, config: { ...n.data.config } } })),
          edges: selectedEdges.map((e) => ({ ...e })),
        },
      });
      toast(`已复制 ${selectedNodes.length} 个节点`);
    },

    paste: () => {
      const { clipboard, nodes, edges } = get();
      if (!clipboard || clipboard.nodes.length === 0) return;
      pushSnapshot();
      const idMap = new Map<string, string>();
      for (const n of clipboard.nodes) idMap.set(n.id, newNodeId(n.data.nodeType));
      const newNodes: SchemaFlowNode[] = clipboard.nodes.map((n) => ({
        ...n,
        id: idMap.get(n.id)!,
        position: { x: n.position.x + PASTE_OFFSET, y: n.position.y + PASTE_OFFSET },
        selected: true,
        data: { nodeType: n.data.nodeType, config: { ...n.data.config } },
      }));
      const newEdges: Edge[] = clipboard.edges.map((e) => ({
        ...e,
        id: newEdgeId(),
        source: idMap.get(e.source)!,
        target: idMap.get(e.target)!,
        selected: false,
      }));
      set({
        nodes: [...nodes.map((n) => ({ ...n, selected: false })), ...newNodes],
        edges: [...edges, ...newEdges],
      });
      markDirty();
    },

    undo: () => {
      const { past, future, nodes, edges } = get();
      if (past.length === 0) return;
      const prev = past[past.length - 1];
      set({
        past: past.slice(0, -1),
        future: [...future, { nodes, edges }],
        nodes: prev.nodes,
        edges: prev.edges,
      });
      markDirty();
    },

    redo: () => {
      const { past, future, nodes, edges } = get();
      if (future.length === 0) return;
      const next = future[future.length - 1];
      set({
        future: future.slice(0, -1),
        past: [...past, { nodes, edges }].slice(-UNDO_LIMIT),
        nodes: next.nodes,
        edges: next.edges,
      });
      markDirty();
    },

    updateNodeConfigValue: (nodeId, key, value) => {
      set({
        nodes: get().nodes.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, config: { ...n.data.config, [key]: value } } } : n,
        ),
      });
      markDirty();
    },

    setNodeConfig: (nodeId, config) => {
      set({
        nodes: get().nodes.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, config } } : n)),
      });
      markDirty();
    },

    setWorkflowName: (name) => {
      set({ workflowName: name });
      markDirty();
    },

    setViewport: (viewport) => {
      set({ viewport });
      markDirty();
    },

    serialize: () => {
      const { workflowName, nodes, edges, viewport } = get();
      return {
        version: 1,
        name: workflowName,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.data.nodeType,
          position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
          config: n.data.config,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          source_handle: e.sourceHandle ?? '',
          target: e.target,
          target_handle: e.targetHandle ?? '',
        })),
        viewport,
      };
    },

    loadWorkflow: (record) => {
      if (saveTimer) {
        clearTimeout(saveTimer);
        saveTimer = null;
      }
      const data = record.data;
      const nodes: SchemaFlowNode[] = (data?.nodes ?? []).map((n) => ({
        id: n.id,
        type: 'schemaNode' as const,
        position: { x: n.position.x, y: n.position.y },
        data: { nodeType: n.type, config: n.config ?? {} },
      }));
      const edges: Edge[] = (data?.edges ?? []).map((e) => ({
        id: e.id,
        source: e.source,
        sourceHandle: e.source_handle,
        target: e.target,
        targetHandle: e.target_handle,
      }));
      set({
        workflowId: record.id,
        workflowName: record.name ?? data?.name ?? '未命名工作流',
        nodes,
        edges,
        viewport: data?.viewport ?? { x: 0, y: 0, zoom: 1 },
        dirty: false,
        saveState: 'saved',
        past: [],
        future: [],
      });
      setLastWorkflowId(record.id);
      useRunStore.getState().resetRun();

      // 回填最近一次运行的节点状态与输出：重新打开工作流时预览图/视频立即可见，
      // 而不是全部显示「空闲」像没跑过一样。
      void (async () => {
        try {
          const { data: runs } = await api.listRuns(record.id);
          if (!runs.length) return;
          const sorted = [...runs].sort((a, b) =>
            String(b.started_at ?? '').localeCompare(String(a.started_at ?? '')),
          );
          const latest = sorted.find((r) => r.status === 'success') ?? sorted[0];
          if (!latest) return;
          const { data: full } = await api.getRun(latest.id);
          useRunStore.getState().hydrateFromRun(full);
        } catch {
          // 回填失败不影响画布使用
        }
      })();
    },

    newWorkflow: async () => {
      try {
        const { data } = await api.createWorkflow('未命名工作流');
        get().loadWorkflow(data);
      } catch (e) {
        toast.error('创建工作流失败', e instanceof Error ? e.message : undefined);
        throw e;
      }
    },

    saveWorkflow: async () => {
      const { workflowId } = get();
      if (!workflowId) return;
      if (saveTimer) {
        clearTimeout(saveTimer);
        saveTimer = null;
      }
      set({ saveState: 'saving' });
      try {
        const payload = get().serialize();
        await api.updateWorkflow(workflowId, { name: payload.name, data: payload });
        set({ dirty: false, saveState: 'saved' });
      } catch (e) {
        set({ saveState: 'error' });
        toast.error('保存失败', e instanceof Error ? e.message : undefined);
      }
    },

    markDirty,

    applyNodeStatus: (nodeId, status, error) => {
      useRunStore.getState().setNodeStatus(nodeId, status, error);
    },

    resetStatuses: () => {
      useRunStore.getState().resetRun();
    },
  };
});
