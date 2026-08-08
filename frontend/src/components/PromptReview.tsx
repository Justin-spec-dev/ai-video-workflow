// Prompt Review（§10）：prompt_optimizer 的 Original/Optimized 对比，
// 接受 / 编辑 / 重新生成 / 还原原始 / 复制 —— 编辑写入 config.edited_prompt。
import { Check, ClipboardCopy, Pencil, RotateCcw, Undo2 } from 'lucide-react';
import { useState } from 'react';
import * as api from '../api/resources';
import { ApiError } from '../api/client';
import { useRunStore } from '../stores/runStore';
import { useWorkflowStore } from '../stores/workflowStore';
import { Button } from './ui/button';
import { Textarea } from './ui/input';
import { toast } from './ui/toast';

function str(v: unknown): string {
  return typeof v === 'string' ? v : v == null ? '' : JSON.stringify(v);
}

export function PromptReview({ nodeId }: { nodeId: string }) {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const updateNodeConfigValue = useWorkflowStore((s) => s.updateNodeConfigValue);
  const outputs = useRunStore((s) => s.nodeOutputs[nodeId]);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);

  const original = str(outputs?.original);
  const optimized = str(outputs?.prompt);
  const edited = str(node?.data.config.edited_prompt);
  const effective = edited || optimized || original;

  if (!node) return null;

  const regenerate = async () => {
    if (!workflowId) return;
    setBusy(true);
    try {
      updateNodeConfigValue(nodeId, 'edited_prompt', '');
      await api.runNode(workflowId, nodeId, false);
      toast('正在重新生成提示词…');
    } catch (e) {
      toast.error('重新生成失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-md border border-zinc-800 bg-zinc-900/80 p-2">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-semibold text-zinc-300">提示词审阅</span>
        {edited ? (
          <span className="rounded bg-sky-900/60 px-1.5 py-0.5 text-[9px] font-semibold text-sky-300">
            使用编辑版
          </span>
        ) : null}
      </div>

      <div className="space-y-2">
        <div>
          <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500">原始提示词</div>
          <div className="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-zinc-950 p-1.5 font-mono text-[11px] text-zinc-400">
            {original || <span className="text-zinc-600">— 运行节点后可见 —</span>}
          </div>
        </div>
        <div>
          <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500">优化后</div>
          <div className="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-zinc-950 p-1.5 font-mono text-[11px] text-zinc-300">
            {edited ? edited : optimized || <span className="text-zinc-600">— 运行节点后可见 —</span>}
          </div>
        </div>

        {editing ? (
          <div className="space-y-1">
            <Textarea rows={5} value={draft} onChange={(e) => setDraft(e.target.value)} className="font-mono text-xs" />
            <div className="flex gap-1">
              <Button
                size="xs"
                onClick={() => {
                  updateNodeConfigValue(nodeId, 'edited_prompt', draft);
                  setEditing(false);
                }}
              >
                保存编辑
              </Button>
              <Button size="xs" variant="ghost" onClick={() => setEditing(false)}>
                取消
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1">
            <Button
              size="xs"
              variant="secondary"
              disabled={!optimized}
              title="采用优化后的提示词"
              onClick={() => updateNodeConfigValue(nodeId, 'edited_prompt', optimized)}
            >
              <Check size={11} /> 接受
            </Button>
            <Button
              size="xs"
              variant="secondary"
              onClick={() => {
                setDraft(effective);
                setEditing(true);
              }}
            >
              <Pencil size={11} /> 编辑
            </Button>
            <Button size="xs" variant="secondary" disabled={busy} onClick={() => void regenerate()}>
              <RotateCcw size={11} /> 重新生成
            </Button>
            <Button
              size="xs"
              variant="secondary"
              disabled={!original}
              onClick={() => updateNodeConfigValue(nodeId, 'edited_prompt', original)}
            >
              <Undo2 size={11} /> 还原原始
            </Button>
            <Button
              size="xs"
              variant="secondary"
              disabled={!effective}
              onClick={() => {
                void navigator.clipboard.writeText(effective).then(() => toast.success('已复制到剪贴板'));
              }}
            >
              <ClipboardCopy size={11} /> 复制
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
