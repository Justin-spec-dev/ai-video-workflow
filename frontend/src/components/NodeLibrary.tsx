// 侧栏「节点库」分区（§10）：按分类分组（中文），支持过滤、点击或拖拽添加；分区可独立折叠，与工作流列表互不影响。
import { ChevronDown, ChevronRight, Search } from 'lucide-react';
import { useMemo, useState, type DragEvent } from 'react';
import { cn } from '../lib/utils';
import { categoryLabel, nodeLabel } from '../nodes/labels';
import { useWorkflowStore } from '../stores/workflowStore';
import type { NodeSchema } from '../types';

const CATEGORY_ORDER = ['Input', 'Text', 'Context', 'AI', 'Image', 'Video', 'Logic', 'Utility', 'Output'];

export function NodeLibrary() {
  const schemas = useWorkflowStore((s) => s.nodeSchemas);
  const schemasLoaded = useWorkflowStore((s) => s.schemasLoaded);
  const addNode = useWorkflowStore((s) => s.addNode);
  const [query, setQuery] = useState('');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [sectionCollapsed, setSectionCollapsed] = useState(false);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const map = new Map<string, NodeSchema[]>();
    for (const s of Object.values(schemas)) {
      const label = nodeLabel(s.type);
      if (
        q &&
        !s.name.toLowerCase().includes(q) &&
        !s.type.toLowerCase().includes(q) &&
        !label.name.includes(query.trim())
      )
        continue;
      const list = map.get(s.category) ?? [];
      list.push(s);
      map.set(s.category, list);
    }
    const cats = [
      ...CATEGORY_ORDER.filter((c) => map.has(c)),
      ...[...map.keys()].filter((c) => !CATEGORY_ORDER.includes(c)).sort(),
    ];
    return cats.map((category) => ({
      category,
      items: map.get(category)!.sort((a, b) => nodeLabel(a.type).name.localeCompare(nodeLabel(b.type).name, 'zh')),
    }));
  }, [schemas, query]);

  const onDragStart = (e: DragEvent, nodeType: string) => {
    e.dataTransfer.setData('application/aivwf-node', nodeType);
    e.dataTransfer.effectAllowed = 'move';
  };

  // 点击添加：落在画布可见区域附近，带少量随机错位。
  const addByClick = (nodeType: string) => {
    addNode(nodeType, { x: 120 + Math.random() * 160, y: 80 + Math.random() * 160 });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-9 shrink-0 items-center px-2">
        <button
          type="button"
          onClick={() => setSectionCollapsed((c) => !c)}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300"
        >
          {sectionCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
          节点库
        </button>
      </div>
      {!sectionCollapsed ? (
        <>
          <div className="flex h-9 shrink-0 items-center gap-2 border-t border-zinc-800 px-3">
            <Search size={13} className="shrink-0 text-zinc-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="筛选节点…"
              className="h-7 w-full bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto py-1.5">
            {!schemasLoaded ? (
              <div className="px-3 py-4 text-xs text-zinc-500">正在加载节点定义…</div>
            ) : groups.length === 0 ? (
              <div className="px-3 py-4 text-xs text-zinc-500">没有匹配的节点</div>
            ) : (
              groups.map((group) => {
                const isCollapsed = collapsed[group.category] && !query;
                return (
                  <div key={group.category}>
                    <button
                      type="button"
                      onClick={() => setCollapsed((c) => ({ ...c, [group.category]: !c[group.category] }))}
                      className="flex w-full items-center justify-between px-3 pb-1 pt-2.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300"
                    >
                      {categoryLabel(group.category)}
                      <span className="text-zinc-600">{group.items.length}</span>
                    </button>
                    {!isCollapsed
                      ? group.items.map((s) => {
                          const label = nodeLabel(s.type);
                          return (
                            <div
                              key={s.type}
                              draggable
                              onDragStart={(e) => onDragStart(e, s.type)}
                              onClick={() => addByClick(s.type)}
                              title={label.description || s.description}
                              className={cn(
                                'mx-1.5 mb-0.5 cursor-grab rounded-md border border-transparent px-2 py-1.5 transition-colors',
                                'hover:border-zinc-700 hover:bg-zinc-800 active:cursor-grabbing',
                              )}
                            >
                              <div className="flex items-center justify-between gap-1">
                                <span className="truncate text-xs text-zinc-200">{label.name}</span>
                                {s.is_paid ? (
                                  <span className="shrink-0 rounded bg-amber-900/70 px-1 text-[9px] font-semibold text-amber-300">
                                    ¥
                                  </span>
                                ) : null}
                              </div>
                              {label.description ? (
                                <div className="truncate text-[10px] text-zinc-500">{label.description}</div>
                              ) : null}
                            </div>
                          );
                        })
                      : null}
                  </div>
                );
              })
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
