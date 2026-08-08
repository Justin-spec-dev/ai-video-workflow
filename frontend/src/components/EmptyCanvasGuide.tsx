// 空画布引导卡（需求 3）：显眼入口直达快速开始。
import { MousePointerClick, Space, Sparkles } from 'lucide-react';
import { useUIStore } from '../stores/uiStore';
import { Button } from './ui/button';

export function EmptyCanvasGuide() {
  const setQuickStartOpen = useUIStore((s) => s.setQuickStartOpen);

  return (
    <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center">
      <div className="pointer-events-auto flex w-[380px] flex-col items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/90 px-6 py-6 text-center shadow-2xl shadow-black/50 backdrop-blur">
        <span className="flex h-10 w-10 items-center justify-center rounded-full border border-sky-800 bg-sky-950/60">
          <Sparkles size={18} className="text-sky-400" />
        </span>
        <div>
          <div className="text-sm font-semibold text-zinc-100">从这里开始</div>
          <p className="mt-1 text-xs leading-relaxed text-zinc-500">
            选择一个场景模板，填入提示词与参数， 自动搭好整条视频生产线。
          </p>
        </div>
        <Button size="md" className="font-semibold" onClick={() => setQuickStartOpen(true)}>
          <Sparkles size={14} /> 快速开始
        </Button>
        <div className="flex items-center gap-4 text-[10px] text-zinc-600">
          <span className="flex items-center gap-1">
            <Space size={11} /> 空格键搜索节点
          </span>
          <span className="flex items-center gap-1">
            <MousePointerClick size={11} /> 双击空白处快速添加
          </span>
        </div>
      </div>
    </div>
  );
}
