// 左侧侧栏：「工作流」+「节点库」两个可独立折叠的分区；整栏可收起为窄条（状态持久化）。
import { PanelLeftOpen } from 'lucide-react';
import { useUIStore } from '../stores/uiStore';
import { NodeLibrary } from './NodeLibrary';
import { WorkflowList } from './WorkflowList';

export function Sidebar() {
  const libraryCollapsed = useUIStore((s) => s.libraryCollapsed);
  const toggleLibrary = useUIStore((s) => s.toggleLibrary);

  if (libraryCollapsed) {
    return (
      <aside className="flex w-9 shrink-0 flex-col items-center border-r border-zinc-800 bg-zinc-900/60 py-2">
        <button
          type="button"
          onClick={toggleLibrary}
          title="展开侧栏"
          className="rounded-md p-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
        >
          <PanelLeftOpen size={15} />
        </button>
        <span className="mt-3 select-none text-[10px] tracking-widest text-zinc-600 [writing-mode:vertical-lr]">
          工作流
        </span>
        <span className="mt-3 select-none text-[10px] tracking-widest text-zinc-600 [writing-mode:vertical-lr]">
          节点库
        </span>
      </aside>
    );
  }

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-zinc-800 bg-zinc-900/60">
      <WorkflowList />
      <NodeLibrary />
    </aside>
  );
}
