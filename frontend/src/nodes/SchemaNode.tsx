// SchemaNode：由后端 NodeSchema 驱动的通用节点（§3）。
// 标题栏：分类图标 + 中文名 + 状态图标 + 中文状态文字（不只靠颜色，§10）。
// Handle：左入右出，按端口类型着色（§2/§10）；数组端口为环形样式。
import { Handle, Position, type NodeProps } from '@xyflow/react';
import {
  AlertTriangle,
  Ban,
  Brain,
  CheckCircle2,
  Circle,
  Clock,
  Database,
  FileInput,
  FileOutput,
  Image as ImageIcon,
  Loader2,
  SlidersHorizontal,
  Type,
  Wrench,
  XCircle,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { memo } from 'react';
import { cn } from '../lib/utils';
import { useRunStore } from '../stores/runStore';
import { useWorkflowStore } from '../stores/workflowStore';
import type { MediaValue, NodeStatus } from '../types';
import type { SchemaFlowNode } from '../types/rf';
import { nodeLabel, statusLabel } from './labels';
import { portHandleStyle } from './portColors';

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  Input: FileInput,
  Text: Type,
  Context: SlidersHorizontal,
  AI: Brain,
  Image: ImageIcon,
  Video: Zap,
  Logic: SlidersHorizontal,
  Utility: Wrench,
  Output: FileOutput,
};

const STATUS_META: Record<NodeStatus, { icon: LucideIcon; className: string; spin?: boolean }> = {
  IDLE: { icon: Circle, className: 'text-zinc-500' },
  QUEUED: { icon: Clock, className: 'text-zinc-400' },
  WAITING_CONFIRMATION: { icon: AlertTriangle, className: 'text-amber-400' },
  RUNNING: { icon: Loader2, className: 'text-sky-400', spin: true },
  SUCCESS: { icon: CheckCircle2, className: 'text-emerald-400' },
  FAILED: { icon: XCircle, className: 'text-red-400' },
  CACHED: { icon: Database, className: 'text-teal-400' },
  CANCELLED: { icon: Ban, className: 'text-zinc-500' },
};

// 卡片边框 + 顶部状态色条
const STATUS_CARD: Record<NodeStatus, string> = {
  IDLE: 'border-zinc-700/80',
  QUEUED: 'border-zinc-500',
  WAITING_CONFIRMATION: 'border-amber-600',
  RUNNING: 'border-sky-500 shadow-[0_0_16px_rgba(56,189,248,0.28)]',
  SUCCESS: 'border-emerald-700/80',
  FAILED: 'border-red-600',
  CACHED: 'border-teal-700/80',
  CANCELLED: 'border-zinc-700 opacity-70',
};

const STATUS_BAR: Record<NodeStatus, string> = {
  IDLE: 'bg-zinc-700',
  QUEUED: 'bg-zinc-500',
  WAITING_CONFIRMATION: 'bg-amber-500',
  RUNNING: 'bg-sky-500',
  SUCCESS: 'bg-emerald-500',
  FAILED: 'bg-red-500',
  CACHED: 'bg-teal-500',
  CANCELLED: 'bg-zinc-600',
};

const PORT_ROW = 22;

function asMedia(value: unknown): MediaValue | null {
  if (value && typeof value === 'object' && 'url' in value && typeof (value as MediaValue).url === 'string') {
    return value as MediaValue;
  }
  return null;
}

function SchemaNode({ id, data, selected }: NodeProps<SchemaFlowNode>) {
  const schema = useWorkflowStore((s) => s.nodeSchemas[data.nodeType]);
  const statusInfo = useRunStore((s) => s.nodeStatuses[id]);
  const outputs = useRunStore((s) => s.nodeOutputs[id]);

  const status: NodeStatus = statusInfo?.status ?? 'IDLE';
  const statusMeta = STATUS_META[status];
  const StatusIcon = statusMeta.icon;
  const CategoryIcon = CATEGORY_ICONS[schema?.category ?? ''] ?? Wrench;

  if (!schema) {
    return (
      <div className="w-[248px] rounded-lg border border-red-700 bg-zinc-900 p-2 text-xs text-red-300">
        未知节点类型：{data.nodeType}
      </div>
    );
  }

  const label = nodeLabel(data.nodeType);
  const inputs = schema.inputs;
  const outputsPorts = schema.outputs;
  const rows = Math.max(inputs.length, outputsPorts.length);

  // 内嵌预览（§10）：所有产出视频/图片的节点都直接内嵌预览，无需额外挂预览节点。
  const VIDEO_PREVIEW_TYPES = ['video_preview', 'video_generation', 'video_merge'];
  const IMAGE_PREVIEW_TYPES = ['last_frame', 'frame_extract', 'image_input'];
  const videoMedia = VIDEO_PREVIEW_TYPES.includes(data.nodeType) ? asMedia(outputs?.video) : null;
  const imageMedia = IMAGE_PREVIEW_TYPES.includes(data.nodeType) ? asMedia(outputs?.image) : null;
  const hasPreview = Boolean(videoMedia || imageMedia || statusInfo?.error);

  return (
    <div
      className={cn(
        'w-[248px] overflow-hidden rounded-lg border bg-zinc-900 text-xs shadow-md shadow-black/40 transition-shadow',
        STATUS_CARD[status],
        selected && 'shadow-lg shadow-black/60 ring-1 ring-sky-400',
      )}
    >
      {/* 顶部状态色条 */}
      <div className={cn('h-[3px] w-full', STATUS_BAR[status])} />

      {/* 标题栏 */}
      <div className="flex items-center gap-1.5 border-b border-zinc-800 bg-zinc-800/60 px-2.5 py-1.5">
        <CategoryIcon size={13} className="shrink-0 text-zinc-400" />
        <span className="min-w-0 flex-1 truncate font-medium text-zinc-100" title={label.description || label.name}>
          {label.name}
        </span>
        {schema.is_paid ? (
          <span
            className="shrink-0 rounded bg-amber-900/70 px-1 text-[9px] font-semibold text-amber-300"
            title="付费节点"
          >
            ¥
          </span>
        ) : null}
        <StatusIcon size={12} className={cn('shrink-0', statusMeta.className, statusMeta.spin && 'animate-spin')} />
        <span className={cn('shrink-0 text-[10px] font-medium', statusMeta.className)}>{statusLabel(status)}</span>
      </div>

      {/* 端口区 */}
      <div className="relative py-1" style={{ height: rows * PORT_ROW + 8 }}>
        {inputs.map((port, i) => (
          <div
            key={port.key}
            className="absolute left-0 flex items-center pl-3 text-[11px] text-zinc-400"
            style={{ top: i * PORT_ROW + 4, height: PORT_ROW }}
          >
            <Handle
              type="target"
              id={port.key}
              position={Position.Left}
              style={{ ...portHandleStyle(port.type), top: '50%', transform: 'translateY(-50%)' }}
              title={`${port.name}：${port.type}${port.required ? '（必填）' : ''}`}
            />
            <span className="truncate">
              {port.name}
              {port.required ? <span className="text-red-400"> *</span> : null}
              {port.multiple ? <span className="text-zinc-600"> [多]</span> : null}
            </span>
          </div>
        ))}
        {outputsPorts.map((port, i) => (
          <div
            key={port.key}
            className="absolute right-0 flex items-center pr-3 text-[11px] text-zinc-400"
            style={{ top: i * PORT_ROW + 4, height: PORT_ROW }}
          >
            <Handle
              type="source"
              id={port.key}
              position={Position.Right}
              style={{ ...portHandleStyle(port.type), top: '50%', transform: 'translateY(-50%)' }}
              title={`${port.name}：${port.type}`}
            />
            <span className="truncate">{port.name}</span>
          </div>
        ))}
      </div>

      {/* 预览 / 错误 */}
      {hasPreview ? (
        <div className="nodrag nowheel border-t border-zinc-800 p-1.5">
          {videoMedia ? (
            <video controls src={videoMedia.url} className="w-full rounded bg-black" style={{ maxHeight: 160 }} />
          ) : null}
          {imageMedia ? (
            <img
              src={imageMedia.url}
              alt={imageMedia.filename ?? '预览'}
              className="w-full cursor-zoom-in rounded bg-black object-contain"
              style={{ maxHeight: 160 }}
              onClick={() => window.open(imageMedia.url, '_blank')}
            />
          ) : null}
          {statusInfo?.error ? (
            <div className="mt-1 max-h-16 overflow-y-auto whitespace-pre-wrap break-words rounded bg-red-950/60 p-1.5 font-mono text-[10px] text-red-300">
              {statusInfo.error}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default memo(SchemaNode);
