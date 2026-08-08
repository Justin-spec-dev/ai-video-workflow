// 付费运行确认弹窗（SPEC §5.7/§10）。
import { useUIStore } from '../stores/uiStore';
import { Button } from './ui/button';
import { Dialog } from './ui/dialog';
import { confirmPaidRun } from './TopBar';

export function EstimateDialog() {
  const open = useUIStore((s) => s.estimateOpen);
  const estimate = useUIStore((s) => s.estimate);
  const closeEstimate = useUIStore((s) => s.closeEstimate);
  const runBusy = useUIStore((s) => s.runBusy);

  if (!estimate) return null;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => (v ? undefined : closeEstimate())}
      title="确认付费运行"
      description="当前工作流包含付费节点，请在运行前确认预估信息。"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={closeEstimate}>
            取消
          </Button>
          <Button
            variant="success"
            size="sm"
            disabled={runBusy}
            onClick={() => {
              closeEstimate();
              void confirmPaidRun(estimate);
            }}
          >
            确认并运行
          </Button>
        </>
      }
    >
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-zinc-400">付费节点数</dt>
        <dd className="text-right font-mono text-zinc-100">{estimate.paid_node_count}</dd>
        <dt className="text-zinc-400">预估 API 调用</dt>
        <dd className="text-right font-mono text-zinc-100">{estimate.estimated_api_calls}</dd>
        <dt className="text-zinc-400">预估视频时长</dt>
        <dd className="text-right font-mono text-zinc-100">{estimate.estimated_video_seconds} 秒</dd>
        <dt className="text-zinc-400">预估费用</dt>
        <dd className="text-right font-mono text-zinc-100">
          {estimate.estimated_cost === null ? (
            <span className="text-amber-400">费用未知</span>
          ) : (
            `${estimate.estimated_cost.toFixed(4)} ${estimate.currency}`
          )}
        </dd>
      </dl>
      {estimate.notes.length > 0 ? (
        <ul className="mt-3 list-disc space-y-0.5 pl-4 text-[11px] text-zinc-500">
          {estimate.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      ) : null}
    </Dialog>
  );
}
