// 底部面板（§10）：日志 / 任务 / 运行 / 成本 四个 Tab。
import { ClipboardCopy, ExternalLink, RefreshCw, Square } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as api from '../api/resources';
import { ApiError } from '../api/client';
import { cn, formatClock, formatTime, shortId } from '../lib/utils';
import { nodeLabel, runStatusLabel, taskStatusLabel } from '../nodes/labels';
import { useRunStore } from '../stores/runStore';
import { useWorkflowStore } from '../stores/workflowStore';
import type { ProviderTask } from '../types';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Select } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { toast } from './ui/toast';

// ---------------- 日志 ----------------

const LEVEL_COLORS: Record<string, string> = {
  debug: 'text-zinc-500',
  info: 'text-zinc-300',
  warning: 'text-amber-400',
  warn: 'text-amber-400',
  error: 'text-red-400',
};

function LogsTab() {
  const logs = useRunStore((s) => s.logs);
  const nodes = useWorkflowStore((s) => s.nodes);
  const [query, setQuery] = useState('');
  const [nodeFilter, setNodeFilter] = useState('');
  const [levelFilter, setLevelFilter] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return logs.filter(
      (l) =>
        (!q || l.message.toLowerCase().includes(q)) &&
        (!nodeFilter || l.node_id === nodeFilter) &&
        (!levelFilter || l.level.toLowerCase() === levelFilter),
    );
  }, [logs, query, nodeFilter, levelFilter]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [filtered.length]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-zinc-800 px-2 py-1">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索日志…"
          className="h-6 w-48 rounded border border-zinc-700 bg-zinc-900 px-1.5 text-[11px] text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
        <Select value={nodeFilter} onChange={(e) => setNodeFilter(e.target.value)} className="h-6 w-40 text-[11px]">
          <option value="">全部节点</option>
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {nodeLabel(n.data.nodeType).name}（{shortId(n.id, 6)}）
            </option>
          ))}
        </Select>
        <Select value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)} className="h-6 w-28 text-[11px]">
          <option value="">全部级别</option>
          <option value="debug">debug</option>
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="error">error</option>
        </Select>
        <div className="flex-1" />
        <Button
          variant="ghost"
          size="xs"
          onClick={() => {
            const text = filtered
              .map((l) => `[${formatClock(l.ts)}] [${l.level}] ${l.node_id ? `[${l.node_id}] ` : ''}${l.message}`)
              .join('\n');
            void navigator.clipboard.writeText(text).then(() => toast.success(`已复制 ${filtered.length} 条日志`));
          }}
        >
          <ClipboardCopy size={11} /> 复制
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-1 font-mono text-[11px] leading-5">
        {filtered.length === 0 ? (
          <div className="py-3 text-center text-zinc-600">暂无日志</div>
        ) : (
          filtered.map((l, i) => (
            <div key={i} className="whitespace-pre-wrap break-all">
              <span className="text-zinc-600">{formatClock(l.ts)} </span>
              <span className={cn('uppercase', LEVEL_COLORS[l.level.toLowerCase()] ?? 'text-zinc-300')}>
                [{l.level}]
              </span>{' '}
              {l.node_id ? <span className="text-sky-500">[{shortId(l.node_id, 10)}] </span> : null}
              <span className="text-zinc-300">{l.message}</span>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

// ---------------- 任务 ----------------

function taskOutputUrl(task: ProviderTask): string | null {
  const out = task.output;
  if (out && typeof out === 'object' && 'url' in out && typeof (out as { url: unknown }).url === 'string') {
    return (out as { url: string }).url;
  }
  return null;
}

function TasksTab() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const tasks = useRunStore((s) => s.tasks);
  const setTasks = useRunStore((s) => s.setTasks);
  const upsertTask = useRunStore((s) => s.upsertTask);
  const [loading, setLoading] = useState(false);

  const reload = async () => {
    setLoading(true);
    try {
      const { data } = await api.listTasks(workflowId ? { workflow_id: workflowId } : undefined);
      setTasks(data);
    } catch (e) {
      toast.error('任务加载失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

  const refreshOne = async (id: string) => {
    try {
      const { data } = await api.refreshTask(id);
      upsertTask(data);
    } catch (e) {
      toast.error('刷新失败', e instanceof ApiError ? e.detail : undefined);
    }
  };

  const cancelOne = async (id: string) => {
    try {
      const { data } = await api.cancelTask(id);
      upsertTask(data);
      toast.success('任务已取消');
    } catch (e) {
      toast.error('取消失败', e instanceof ApiError ? e.detail : '该 provider 可能不支持取消');
    }
  };

  const active = (t: ProviderTask) => t.status === 'queued' || t.status === 'running';

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-end border-b border-zinc-800 px-2 py-1">
        <Button variant="ghost" size="xs" disabled={loading} onClick={() => void reload()}>
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} /> 刷新
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-left text-[11px]">
          <thead className="sticky top-0 bg-zinc-900 text-zinc-500">
            <tr>
              <th className="px-2 py-1 font-medium">任务</th>
              <th className="px-2 py-1 font-medium">节点</th>
              <th className="px-2 py-1 font-medium">Provider / 模型</th>
              <th className="px-2 py-1 font-medium">远端 ID</th>
              <th className="px-2 py-1 font-medium">状态</th>
              <th className="px-2 py-1 font-medium">创建时间</th>
              <th className="px-2 py-1 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-2 py-3 text-center text-zinc-600">
                  暂无任务
                </td>
              </tr>
            ) : (
              tasks.map((t) => {
                const url = taskOutputUrl(t);
                return (
                  <tr key={t.id} className="border-t border-zinc-800/60 hover:bg-zinc-800/30">
                    <td className="px-2 py-1 font-mono" title={t.id}>{shortId(t.id)}</td>
                    <td className="px-2 py-1 font-mono" title={t.node_id}>{shortId(t.node_id, 10)}</td>
                    <td className="px-2 py-1">
                      {t.provider}
                      {t.model ? <span className="text-zinc-500"> / {t.model}</span> : null}
                    </td>
                    <td className="px-2 py-1 font-mono text-zinc-400" title={t.remote_task_id ?? ''}>
                      {t.remote_task_id ? shortId(t.remote_task_id, 12) : '—'}
                    </td>
                    <td className="px-2 py-1">
                      <Badge
                        variant={
                          t.status === 'succeeded' ? 'success' : t.status === 'failed' ? 'danger' : active(t) ? 'warning' : 'muted'
                        }
                      >
                        {taskStatusLabel(t.status)}
                      </Badge>
                      {t.error ? <div className="max-w-40 truncate text-[10px] text-red-400" title={t.error}>{t.error}</div> : null}
                    </td>
                    <td className="px-2 py-1 text-zinc-500">{formatTime(t.created_at)}</td>
                    <td className="px-2 py-1">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="xs" onClick={() => void refreshOne(t.id)}>
                          <RefreshCw size={11} /> 刷新
                        </Button>
                        <Button
                          variant="ghost"
                          size="xs"
                          disabled={!active(t)}
                          title={active(t) ? '取消远端任务（需 provider 支持）' : '任务已结束'}
                          onClick={() => void cancelOne(t.id)}
                        >
                          <Square size={11} /> 取消
                        </Button>
                        <Button
                          variant="ghost"
                          size="xs"
                          disabled={!url}
                          onClick={() => url && window.open(url, '_blank')}
                        >
                          <ExternalLink size={11} /> 查看结果
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------- 运行 ----------------

function RunsTab() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const runs = useRunStore((s) => s.runs);
  const setRuns = useRunStore((s) => s.setRuns);
  const [loading, setLoading] = useState(false);

  const reload = async () => {
    if (!workflowId) return;
    setLoading(true);
    try {
      const { data } = await api.listRuns(workflowId);
      setRuns(data);
    } catch (e) {
      toast.error('运行记录加载失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

  const stop = async (id: string) => {
    try {
      await api.stopRun(id);
      void reload();
    } catch (e) {
      toast.error('停止失败', e instanceof ApiError ? e.detail : undefined);
    }
  };

  const resume = async (id: string) => {
    try {
      await api.resumeRun(id);
      toast.success('已继续运行');
      void reload();
    } catch (e) {
      toast.error('继续失败', e instanceof ApiError ? e.detail : undefined);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-end border-b border-zinc-800 px-2 py-1">
        <Button variant="ghost" size="xs" disabled={loading} onClick={() => void reload()}>
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} /> 刷新
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-left text-[11px]">
          <thead className="sticky top-0 bg-zinc-900 text-zinc-500">
            <tr>
              <th className="px-2 py-1 font-medium">运行</th>
              <th className="px-2 py-1 font-medium">状态</th>
              <th className="px-2 py-1 font-medium">触发方式</th>
              <th className="px-2 py-1 font-medium">开始时间</th>
              <th className="px-2 py-1 font-medium">结束时间</th>
              <th className="px-2 py-1 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-2 py-3 text-center text-zinc-600">
                  暂无运行记录
                </td>
              </tr>
            ) : (
              runs.map((r) => (
                <tr key={r.id} className="border-t border-zinc-800/60 hover:bg-zinc-800/30">
                  <td className="px-2 py-1 font-mono" title={r.id}>{shortId(r.id)}</td>
                  <td className="px-2 py-1">
                    <Badge
                      variant={
                        r.status === 'success' ? 'success' : r.status === 'failed' ? 'danger' : r.status === 'running' ? 'warning' : 'muted'
                      }
                    >
                      {runStatusLabel(r.status)}
                    </Badge>
                    {r.error ? <div className="max-w-48 truncate text-[10px] text-red-400" title={r.error}>{r.error}</div> : null}
                  </td>
                  <td className="px-2 py-1 text-zinc-400">{r.trigger ?? '—'}</td>
                  <td className="px-2 py-1 text-zinc-500">{formatTime(r.started_at)}</td>
                  <td className="px-2 py-1 text-zinc-500">{formatTime(r.finished_at)}</td>
                  <td className="px-2 py-1">
                    <div className="flex justify-end gap-1">
                      {r.status === 'running' || r.status === 'waiting_confirmation' ? (
                        <Button variant="ghost" size="xs" onClick={() => void stop(r.id)}>
                          <Square size={11} /> 停止
                        </Button>
                      ) : null}
                      <Button variant="ghost" size="xs" onClick={() => void resume(r.id)}>
                        <RefreshCw size={11} /> 继续
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------- 成本 ----------------

function CostTab() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const estimate = useRunStore((s) => s.estimate);
  const setEstimate = useRunStore((s) => s.setEstimate);
  const [loading, setLoading] = useState(false);

  const reEstimate = async () => {
    if (!workflowId) return;
    setLoading(true);
    try {
      await useWorkflowStore.getState().saveWorkflow();
      const { data } = await api.estimateWorkflow(workflowId);
      setEstimate(data);
    } catch (e) {
      toast.error('估算失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold text-zinc-300">当前成本估算</span>
        <Button variant="secondary" size="xs" disabled={!workflowId || loading} onClick={() => void reEstimate()}>
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} /> 估算当前工作流
        </Button>
      </div>
      {!estimate ? (
        <div className="text-[11px] text-zinc-600">暂无估算，点击「估算当前工作流」。</div>
      ) : (
        <div className="max-w-md space-y-2">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
            <dt className="text-zinc-500">付费节点数</dt>
            <dd className="text-right font-mono text-zinc-200">{estimate.paid_node_count}</dd>
            <dt className="text-zinc-500">预估 API 调用</dt>
            <dd className="text-right font-mono text-zinc-200">{estimate.estimated_api_calls}</dd>
            <dt className="text-zinc-500">预估视频时长</dt>
            <dd className="text-right font-mono text-zinc-200">{estimate.estimated_video_seconds} 秒</dd>
            <dt className="text-zinc-500">预估费用</dt>
            <dd className="text-right font-mono text-zinc-200">
              {estimate.estimated_cost === null ? (
                <span className="text-amber-400">费用未知</span>
              ) : (
                `${estimate.estimated_cost.toFixed(4)} ${estimate.currency}`
              )}
            </dd>
          </dl>
          {estimate.notes.length > 0 ? (
            <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-zinc-500">
              {estimate.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          ) : null}
          <p className="text-[10px] text-zinc-600">
            提示：在设置（PUT /api/settings）中填写 <span className="font-mono">pricing.minimax.per_second</span>{' '}
            即可启用费用估算。
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------- 面板 ----------------

export function BottomPanel() {
  const [tab, setTab] = useState('logs');
  const logCount = useRunStore((s) => s.logs.length);
  const taskCount = useRunStore((s) => s.tasks.length);

  return (
    <div className="h-56 shrink-0 border-t border-zinc-800 bg-zinc-900/70">
      <Tabs value={tab} onValueChange={setTab} className="h-full">
        <TabsList>
          <TabsTrigger value="logs">日志（{logCount}）</TabsTrigger>
          <TabsTrigger value="tasks">任务（{taskCount}）</TabsTrigger>
          <TabsTrigger value="runs">运行</TabsTrigger>
          <TabsTrigger value="cost">成本</TabsTrigger>
        </TabsList>
        <TabsContent value="logs">
          <LogsTab />
        </TabsContent>
        <TabsContent value="tasks">
          <TasksTab />
        </TabsContent>
        <TabsContent value="runs">
          <RunsTab />
        </TabsContent>
        <TabsContent value="cost">
          <CostTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
