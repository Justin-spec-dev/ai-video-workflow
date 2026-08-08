// 节点搜索面板（§10）：模糊搜索（含中文名）、分类分组、键盘上下/回车/Esc。
import { Search } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { cn } from '../lib/utils';
import { categoryLabel, nodeLabel } from '../nodes/labels';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';
import type { NodeSchema } from '../types';

const CATEGORY_ORDER = ['Input', 'Text', 'Context', 'AI', 'Image', 'Video', 'Logic', 'Utility', 'Output'];

export function NodeSearch() {
  const { open, flowX, flowY } = useUIStore((s) => s.nodeSearch);
  const closeNodeSearch = useUIStore((s) => s.closeNodeSearch);
  const schemas = useWorkflowStore((s) => s.nodeSchemas);
  const addNode = useWorkflowStore((s) => s.addNode);

  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const all = useMemo(() => Object.values(schemas), [schemas]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = q
      ? all.filter(
          (s) =>
            s.name.toLowerCase().includes(q) ||
            s.type.toLowerCase().includes(q) ||
            (s.description ?? '').toLowerCase().includes(q) ||
            s.category.toLowerCase().includes(q) ||
            nodeLabel(s.type).name.includes(query.trim()) ||
            nodeLabel(s.type).description.includes(query.trim()),
        )
      : all;
    const groups = new Map<string, NodeSchema[]>();
    for (const s of matches) {
      const list = groups.get(s.category) ?? [];
      list.push(s);
      groups.set(s.category, list);
    }
    const orderedCats = [
      ...CATEGORY_ORDER.filter((c) => groups.has(c)),
      ...[...groups.keys()].filter((c) => !CATEGORY_ORDER.includes(c)).sort(),
    ];
    return orderedCats.map((category) => ({ category, items: groups.get(category)! }));
  }, [all, query]);

  const flat = useMemo(() => filtered.flatMap((g) => g.items), [filtered]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (activeIndex >= flat.length) setActiveIndex(Math.max(0, flat.length - 1));
    const el = listRef.current?.querySelector(`[data-index="${activeIndex}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, flat.length]);

  if (!open) return null;

  const pick = (schema: NodeSchema) => {
    addNode(schema.type, { x: flowX, y: flowY });
    closeNodeSearch();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, flat.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const schema = flat[activeIndex];
      if (schema) pick(schema);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeNodeSearch();
    }
  };

  let runningIndex = -1;

  return (
    <div className="absolute inset-0 z-30 flex items-start justify-center pt-[15%]" onClick={closeNodeSearch}>
      <div
        className="w-[440px] overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900 shadow-2xl shadow-black/60"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-zinc-800 px-3">
          <Search size={14} className="text-zinc-500" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="搜索节点（支持中文名）…"
            className="h-10 w-full bg-transparent text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
          />
        </div>
        <div ref={listRef} className="max-h-[320px] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div className="px-3 py-4 text-center text-xs text-zinc-500">没有匹配的节点</div>
          ) : (
            filtered.map((group) => (
              <div key={group.category}>
                <div className="px-3 pb-0.5 pt-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                  {categoryLabel(group.category)}
                </div>
                {group.items.map((schema) => {
                  runningIndex += 1;
                  const idx = runningIndex;
                  const label = nodeLabel(schema.type);
                  return (
                    <button
                      key={schema.type}
                      type="button"
                      data-index={idx}
                      onMouseEnter={() => setActiveIndex(idx)}
                      onClick={() => pick(schema)}
                      className={cn(
                        'flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left',
                        idx === activeIndex ? 'bg-sky-900/40' : '',
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-xs text-zinc-100">{label.name}</span>
                        {label.description ? (
                          <span className="block truncate text-[10px] text-zinc-500">{label.description}</span>
                        ) : null}
                      </span>
                      <span className="flex shrink-0 items-center gap-1">
                        {schema.is_paid ? (
                          <span className="rounded bg-amber-900/70 px-1 text-[9px] font-semibold text-amber-300">¥</span>
                        ) : null}
                        <span className="font-mono text-[10px] text-zinc-600">{schema.type}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
