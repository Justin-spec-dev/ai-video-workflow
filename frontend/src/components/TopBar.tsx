// 顶栏（SPEC §10）：产品名、可编辑 workflow 名、运行/停止、模板菜单、凭证入口、保存状态。
import {
  CheckCircle2,
  CircleDashed,
  FilePlus2,
  FolderOpen,
  KeyRound,
  Loader2,
  Play,
  Sparkles,
  Square,
  Trash2,
  TriangleAlert,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import * as api from '../api/resources';
import { ApiError } from '../api/client';
import { templateLabel } from '../nodes/labels';
import { useCredentialStore } from '../stores/credentialStore';
import { useRunStore } from '../stores/runStore';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';
import type { CostEstimate, Template, WorkflowRun, WorkflowSummary } from '../types';
import {
  DEFAULT_DURATION,
  DEFAULT_LLM_MODEL,
  DEFAULT_RATIO,
  DEFAULT_RESOLUTION,
  DEFAULT_VIDEO_MODEL,
  prefillWorkflow,
  uniqueName,
} from '../workflow/prefill';
import { Button } from './ui/button';
import { DropdownItem, DropdownLabel, DropdownMenu, DropdownSeparator } from './ui/dropdown-menu';
import { toast } from './ui/toast';
import { Tooltip } from './ui/tooltip';

function SaveIndicator() {
  const saveState = useWorkflowStore((s) => s.saveState);
  const map = {
    saved: { icon: CheckCircle2, text: '已保存', cls: 'text-emerald-500' },
    saving: { icon: Loader2, text: '保存中…', cls: 'text-zinc-400 animate-spin' },
    dirty: { icon: CircleDashed, text: '未保存', cls: 'text-amber-400' },
    error: { icon: TriangleAlert, text: '保存失败', cls: 'text-red-400' },
  } as const;
  const { icon: Icon, text, cls } = map[saveState];
  return (
    <span className="flex items-center gap-1 text-[11px] text-zinc-500">
      <Icon size={12} className={cls} />
      {text}
    </span>
  );
}

export function TopBar() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const workflowName = useWorkflowStore((s) => s.workflowName);
  const setWorkflowName = useWorkflowStore((s) => s.setWorkflowName);
  const loadWorkflow = useWorkflowStore((s) => s.loadWorkflow);
  const newWorkflow = useWorkflowStore((s) => s.newWorkflow);
  const saveWorkflow = useWorkflowStore((s) => s.saveWorkflow);

  const currentRunId = useRunStore((s) => s.currentRunId);
  const currentRunStatus = useRunStore((s) => s.currentRunStatus);
  const setEstimate = useRunStore((s) => s.setEstimate);
  const wsStatus = useRunStore((s) => s.wsStatus);

  const openEstimate = useUIStore((s) => s.openEstimate);
  const runBusy = useUIStore((s) => s.runBusy);
  const setRunBusy = useUIStore((s) => s.setRunBusy);
  const setCredentialsOpen = useUIStore((s) => s.setCredentialsOpen);
  const setQuickStartOpen = useUIStore((s) => s.setQuickStartOpen);

  const [nameDraft, setNameDraft] = useState(workflowName);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const saveState = useWorkflowStore((s) => s.saveState);

  useEffect(() => setNameDraft(workflowName), [workflowName]);

  useEffect(() => {
    api.getTemplates().then((r) => setTemplates(r.data)).catch(() => undefined);
    api.listWorkflows().then((r) => setWorkflows(r.data)).catch(() => undefined);
    // saveState 变回 saved 时刷新列表——改名/自动保存后「打开工作流」里能看到新名字
  }, [workflowId, saveState]);

  const running = currentRunStatus === 'running' || currentRunStatus === 'waiting_confirmation';

  const commitName = () => {
    const name = nameDraft.trim();
    if (name && name !== workflowName) setWorkflowName(name);
    else setNameDraft(workflowName);
  };

  /** 付费确认流程（§5.7/§10）：estimate → 弹窗 → run(confirm_paid) → 必要时 /confirm。 */
  const startRun = async (confirmPaid: boolean, estimate?: CostEstimate) => {
    if (!workflowId) return;
    const res = await api.runWorkflow(workflowId, { confirm_paid: confirmPaid });
    const data = res.data as WorkflowRun & { run_id?: string; estimate?: CostEstimate };
    if (res.status === 202 || data.status === 'waiting_confirmation') {
      const runId = data.id ?? data.run_id;
      if (estimate) setEstimate(estimate);
      if (runId) await api.confirmRun(runId);
    }
  };

  const onRun = async () => {
    if (!workflowId || runBusy) return;
    setRunBusy(true);
    try {
      await saveWorkflow(); // 保证后端拿到最新图
      const { data: estimate } = await api.estimateWorkflow(workflowId);
      setEstimate(estimate);
      if (estimate.paid_node_count > 0) {
        openEstimate(estimate); // 弹窗确认后走 confirmPaidRun
        return;
      }
      await startRun(false);
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : '运行失败';
      toast.error('运行失败', msg);
    } finally {
      setRunBusy(false);
    }
  };

  const onStop = async () => {
    if (!currentRunId) return;
    try {
      await api.stopRun(currentRunId);
      toast('已请求停止');
    } catch (e) {
      toast.error('停止失败', e instanceof Error ? e.message : undefined);
    }
  };

  const openWorkflowRecord = async (id: string) => {
    if (id === workflowId) return;
    try {
      const { data } = await api.getWorkflow(id);
      loadWorkflow(data);
    } catch (e) {
      toast.error('打开失败', e instanceof Error ? e.message : undefined);
    }
  };

  const deleteWorkflowRecord = async (w: WorkflowSummary) => {
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

  /** File 菜单模板加载（需求 4）：自动预填默认凭证与默认模型/视频参数。 */
  const newFromTemplate = async (tpl: Template) => {
    const data = tpl.data ?? tpl.workflow;
    if (!data) {
      toast.error('模板缺少工作流数据');
      return;
    }
    try {
      const creds = useCredentialStore.getState().credentials;
      const pickDefault = (kind: string) =>
        (creds.find((c) => c.kind === kind && c.is_default) ?? creds.find((c) => c.kind === kind))?.id ?? null;
      const label = templateLabel(tpl.id, tpl.name);
      const { data: existing } = await api.listWorkflows();
      const name = uniqueName(label.name, existing.map((w) => w.name));
      const prefilled = prefillWorkflow(data, {
        llmCredentialId: pickDefault('llm'),
        llmModel: DEFAULT_LLM_MODEL,
        videoCredentialId: pickDefault('video'),
        videoModel: DEFAULT_VIDEO_MODEL,
        resolution: DEFAULT_RESOLUTION,
        duration: DEFAULT_DURATION,
        ratio: DEFAULT_RATIO,
      });
      prefilled.name = name;
      const { data: record } = await api.createWorkflow(name, prefilled);
      loadWorkflow(record);
      toast.success('已从模板创建工作流', name);
    } catch (e) {
      toast.error('模板加载失败', e instanceof Error ? e.message : undefined);
    }
  };

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-zinc-800 bg-zinc-900 px-4 shadow-sm shadow-black/30">
      <span className="text-sm font-semibold tracking-tight text-zinc-100">
        AI 视频<span className="text-sky-400">工作流</span>
      </span>
      <span className="h-4 w-px bg-zinc-800" />

      <input
        value={nameDraft}
        onChange={(e) => setNameDraft(e.target.value)}
        onBlur={commitName}
        onKeyDown={(e) => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
          if (e.key === 'Escape') setNameDraft(workflowName);
        }}
        className="h-7 w-56 rounded border border-transparent bg-transparent px-2 text-sm text-zinc-200 transition-colors hover:border-zinc-700 focus:border-sky-600 focus:outline-none"
        aria-label="工作流名称"
      />
      <SaveIndicator />

      <div className="flex-1" />

      <Tooltip content={wsStatus === 'open' ? '实时通道已连接' : '实时通道未连接'}>
        <span
          className={`h-2 w-2 rounded-full ${wsStatus === 'open' ? 'bg-emerald-500' : 'bg-red-500'}`}
          aria-label={`WebSocket ${wsStatus}`}
        />
      </Tooltip>

      <Button
        size="sm"
        onClick={() => setQuickStartOpen(true)}
        className="border border-sky-700/60 font-semibold"
      >
        <Sparkles size={13} /> 快速开始
      </Button>

      <DropdownMenu trigger={<span className="flex items-center gap-1.5"><FilePlus2 size={14} /> 文件</span>}>
        <DropdownItem onClick={() => void newWorkflow()}>新建空白工作流</DropdownItem>
        <DropdownSeparator />
        <DropdownLabel>从模板新建</DropdownLabel>
        {templates.length === 0 ? (
          <DropdownItem disabled>暂无可用模板</DropdownItem>
        ) : (
          templates.map((t) => (
            <DropdownItem key={t.id ?? t.name} onClick={() => void newFromTemplate(t)}>
              {templateLabel(t.id, t.name).name}
            </DropdownItem>
          ))
        )}
        <DropdownSeparator />
        <DropdownLabel>打开工作流</DropdownLabel>
        {workflows.length === 0 ? (
          <DropdownItem disabled>暂无已保存工作流</DropdownItem>
        ) : (
          workflows.map((w) => (
            <DropdownItem key={w.id} onClick={() => void openWorkflowRecord(w.id)}>
              <FolderOpen size={12} className="text-zinc-500" />
              <span className="truncate">{w.name}</span>
              {w.id === workflowId ? <span className="ml-auto text-[10px] text-sky-400">当前</span> : null}
              <span
                role="button"
                aria-label={`删除 ${w.name}`}
                title="删除此工作流"
                className={`${w.id === workflowId ? '' : 'ml-auto '}rounded p-0.5 text-zinc-600 hover:bg-red-950/60 hover:text-red-400`}
                onClick={(e) => {
                  e.stopPropagation();
                  void deleteWorkflowRecord(w);
                }}
              >
                <Trash2 size={12} />
              </span>
            </DropdownItem>
          ))
        )}
      </DropdownMenu>

      <Button variant="secondary" size="sm" onClick={() => setCredentialsOpen(true)}>
        <KeyRound size={13} /> 凭证
      </Button>

      {running ? (
        <Button variant="destructive" size="sm" onClick={() => void onStop()}>
          <Square size={13} /> 停止
        </Button>
      ) : (
        <Button variant="success" size="sm" disabled={!workflowId || runBusy} onClick={() => void onRun()}>
          {runBusy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} 运行
        </Button>
      )}
    </header>
  );
}

/** EstimateDialog 确认后调用：confirm_paid=true 发起运行，202 时再调 /confirm。 */
export async function confirmPaidRun(estimate: CostEstimate): Promise<void> {
  const { workflowId, saveWorkflow } = useWorkflowStore.getState();
  const { setRunBusy } = useUIStore.getState();
  if (!workflowId) return;
  setRunBusy(true);
  try {
    await saveWorkflow();
    const res = await api.runWorkflow(workflowId, { confirm_paid: true });
    const data = res.data as WorkflowRun & { run_id?: string };
    if (res.status === 202 || data.status === 'waiting_confirmation') {
      const runId = data.id ?? data.run_id;
      if (runId) await api.confirmRun(runId);
    }
    useRunStore.getState().setEstimate(estimate);
  } catch (e) {
    const msg = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : '运行失败';
    toast.error('运行失败', msg);
  } finally {
    setRunBusy(false);
  }
}
