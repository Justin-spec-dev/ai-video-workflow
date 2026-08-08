// 侧栏「工作流」分区：已保存工作流列表，支持打开/新建/删除；分区可独立折叠，与节点库互不影响。
import { ChevronDown, ChevronRight, FilePlus2, FolderOpen, PanelLeftClose, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import * as api from '../api/resources';
import { cn } from '../lib/utils';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';
import type { WorkflowSummary } from '../types';
import { toast } from './ui/toast';

export function WorkflowList() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const saveState = useWorkflowStore((s) => s.saveState);
  const loadWorkflow = useWorkflowStore((s) => s.loadWorkflow);
  const newWorkflow = useWorkflowStore((s) => s.newWorkflow);
  const toggleLibrary = useUIStore((s) => s.toggleLibrary);

  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    api.listWorkflows().then((r) => setWorkflows(r.data)).catch(() => undefined);
    // saveState 变回 saved 时刷新列表——改名/自动保存后能看到新名字
  }, [workflowId, saveState]);

  const openWorkflow = async (id: string) => {
    if (id === workflowId) return;
    try {
      const { data } = await api.getWorkflow(id);
      loadWorkflow(data);
    } catch (e) {
      toast.error('打开失败', e instanceof Error ? e.message : undefined);
    }
  };

  const deleteWorkflow = async (w: WorkflowSummary) => {
    if (!window.confirm(`确定删除工作流「${w.name}」？此操作不可恢复。`)) return;
    try {
      await api.deleteWorkflow(w.id);
      setWorkflows((list) => list.filter((x) => x.id !== w.id));
      toast.success('已删除工作流', w.name);
      if (w.id === workflowId) await newWorkflow(); // 删除当前打开的 → 切换到空白工作流
    } catch (e) {
      toast.error('删除失败', e instanceof Error ? e.message : undefined);
    }
  };

  return (
    <div className="shrink-0 border-b border-zinc-800">
      <div className="flex h-9 items-center gap-1 pl-2 pr-1.5">
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300"
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
          工作流
          <span className="text-zinc-600">{workflows.length}</span>
        </button>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => void newWorkflow()}
          title="新建空白工作流"
          className="rounded-md p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
        >
          <FilePlus2 size={13} />
        </button>
        <button
          type="button"
          onClick={toggleLibrary}
          title="收起侧栏"
          className="rounded-md p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
        >
          <PanelLeftClose size={14} />
        </button>
      </div>
      {!collapsed ? (
        <div className="max-h-44 overflow-y-auto px-1.5 pb-1.5">
          {workflows.length === 0 ? (
            <div className="px-2 py-2 text-xs text-zinc-500">暂无已保存工作流</div>
          ) : (
            workflows.map((w) => (
              <div
                key={w.id}
                role="button"
                tabIndex={0}
                onClick={() => void openWorkflow(w.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void openWorkflow(w.id);
                }}
                title={w.name}
                className={cn(
                  'group flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 transition-colors hover:bg-zinc-800',
                  w.id === workflowId && 'bg-zinc-800/70',
                )}
              >
                <FolderOpen size={12} className="shrink-0 text-zinc-500" />
                <span className="truncate text-xs text-zinc-200">{w.name}</span>
                {w.id === workflowId ? <span className="ml-auto shrink-0 text-[10px] text-sky-400">当前</span> : null}
                <span
                  role="button"
                  aria-label={`删除 ${w.name}`}
                  title="删除此工作流"
                  className={`${w.id === workflowId ? '' : 'ml-auto '}shrink-0 rounded p-0.5 text-zinc-600 hover:bg-red-950/60 hover:text-red-400`}
                  onClick={(e) => {
                    e.stopPropagation();
                    void deleteWorkflow(w);
                  }}
                >
                  <Trash2 size={12} />
                </span>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
