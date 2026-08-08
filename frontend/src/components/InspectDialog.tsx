// 查看输入 / 查看输出弹窗（§10 右键菜单动作）。
// 输出来自 WS 推送的节点产物；输入取自运行详情（§6 GET /api/runs/{id}）。
import { ClipboardCopy } from 'lucide-react';
import { useEffect, useState } from 'react';
import * as api from '../api/resources';
import { nodeLabel } from '../nodes/labels';
import { useRunStore } from '../stores/runStore';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';
import { Button } from './ui/button';
import { Dialog } from './ui/dialog';
import { toast } from './ui/toast';

export function InspectDialog() {
  const inspect = useUIStore((s) => s.inspect);
  const closeInspect = useUIStore((s) => s.closeInspect);
  const currentRunId = useRunStore((s) => s.currentRunId);
  const nodeOutputs = useRunStore((s) => s.nodeOutputs);
  const nodes = useWorkflowStore((s) => s.nodes);

  const [inputData, setInputData] = useState<unknown>(undefined);
  const [loading, setLoading] = useState(false);

  const nodeId = inspect?.nodeId ?? '';
  const node = nodes.find((n) => n.id === nodeId);
  const nodeName = node ? nodeLabel(node.data.nodeType).name : nodeId;

  useEffect(() => {
    if (!inspect || inspect.mode !== 'input') return;
    if (!currentRunId) {
      setInputData(null);
      return;
    }
    setLoading(true);
    api
      .getRun(currentRunId)
      .then(({ data }) => {
        const nr = [...(data.node_runs ?? [])].reverse().find((r) => r.node_id === inspect.nodeId);
        setInputData(nr?.inputs ?? null);
      })
      .catch(() => setInputData(null))
      .finally(() => setLoading(false));
  }, [inspect, currentRunId]);

  if (!inspect) return null;

  const payload = inspect.mode === 'output' ? nodeOutputs[nodeId] ?? null : inputData;
  const text = loading
    ? '加载中…'
    : payload === undefined || payload === null
      ? '暂无数据 —— 请先运行该节点。'
      : JSON.stringify(payload, null, 2);

  return (
    <Dialog
      open={inspect.open}
      onOpenChange={(v) => (v ? undefined : closeInspect())}
      title={`查看${inspect.mode === 'input' ? '输入' : '输出'} —— ${nodeName}`}
      footer={
        <Button
          variant="secondary"
          size="sm"
          disabled={loading || payload == null}
          onClick={() => {
            void navigator.clipboard.writeText(text).then(() => toast.success('已复制'));
          }}
        >
          <ClipboardCopy size={12} /> 复制 JSON
        </Button>
      }
    >
      <pre className="max-h-[50vh] overflow-auto rounded bg-zinc-950 p-2 font-mono text-[11px] text-zinc-300">
        {text}
      </pre>
    </Dialog>
  );
}
