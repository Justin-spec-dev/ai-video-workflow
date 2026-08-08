// 右侧属性面板（§10）：按 config_schema 动态渲染（中文标签走 labels.ts 映射）。
// 提示词优化器特殊布局：优化前后对比置顶，常用项其次，其余折叠进「高级设置」。
import { ChevronDown, ChevronRight, Upload } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import * as api from '../api/resources';
import { ApiError } from '../api/client';
import { cn } from '../lib/utils';
import { fieldLabel, nodeLabel } from '../nodes/labels';
import { useCredentialStore } from '../stores/credentialStore';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';
import type { ConfigField } from '../types';
import { PromptReview } from './PromptReview';
import { Input, Textarea } from './ui/input';
import { Select } from './ui/select';
import { toast } from './ui/toast';

const MODEL_SUGGESTIONS = ['MiniMax-H3', 'deepseek-v4-flash', 'deepseek-v4-pro', 'gpt-4o-mini', 'gpt-4o', 'claude-sonnet-4'];

interface FieldProps {
  nodeId: string;
  field: ConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
}

function FileField({ value, onChange }: FieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const media =
    value && typeof value === 'object' && 'url' in (value as Record<string, unknown>)
      ? (value as { path: string; url: string })
      : null;

  const doUpload = async (file: File) => {
    setUploading(true);
    try {
      const { data } = await api.uploadFile(file);
      onChange(data); // {path, url, width?, height?} —— 后端读取 path（§3 媒体约定）
      toast.success('文件已上传', file.name);
    } catch (e) {
      toast.error('上传失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-1">
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void doUpload(f);
          e.target.value = '';
        }}
      />
      <button
        type="button"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
        className="flex h-8 w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-zinc-600 text-xs text-zinc-300 transition-colors hover:border-zinc-400 hover:bg-zinc-800 disabled:opacity-50"
      >
        <Upload size={12} /> {uploading ? '上传中…' : media ? '重新上传' : '上传文件'}
      </button>
      {media ? (
        <div className="space-y-1">
          <img src={media.url} alt="已上传" className="max-h-28 w-full rounded bg-black object-contain" />
          <div className="truncate font-mono text-[10px] text-zinc-500" title={media.path}>
            {media.path}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ConfigFieldRow({ nodeId, field, value, onChange }: FieldProps) {
  const credentials = useCredentialStore((s) => s.credentials);
  const setCredentialsOpen = useUIStore((s) => s.setCredentialsOpen);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const listId = `dl-${nodeId}-${field.key}`;

  const strValue = value === undefined || value === null ? '' : String(value);

  let control: React.ReactNode;
  switch (field.type) {
    case 'textarea':
      control = (
        <Textarea
          rows={field.rows ?? 4}
          value={strValue}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          className="font-mono text-xs"
        />
      );
      break;
    case 'number':
      control = (
        <Input
          type="number"
          value={strValue}
          min={field.min}
          max={field.max}
          step={field.step}
          onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
        />
      );
      break;
    case 'boolean':
      control = (
        <label className="flex h-8 cursor-pointer items-center gap-2 text-xs text-zinc-300">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
            className="h-3.5 w-3.5 accent-sky-500"
          />
          {Boolean(value) ? '开' : '关'}
        </label>
      );
      break;
    case 'select':
      control = (
        <Select value={strValue} onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {(field.options ?? []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </Select>
      );
      break;
    case 'credential': {
      const kind = field.provider_kind ?? '';
      const options = credentials.filter((c) => !kind || c.kind === kind);
      control = (
        <div className="flex gap-1">
          <Select value={strValue} onChange={(e) => onChange(e.target.value || null)} className="flex-1">
            <option value="">— 未选择 —</option>
            {options.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}（{c.provider}）
              </option>
            ))}
          </Select>
          <button
            type="button"
            onClick={() => setCredentialsOpen(true)}
            className="shrink-0 rounded-md border border-zinc-700 px-2 text-[11px] text-zinc-400 transition-colors hover:bg-zinc-800"
          >
            管理
          </button>
        </div>
      );
      break;
    }
    case 'model':
      control = (
        <>
          <Input
            list={listId}
            value={strValue}
            placeholder={field.placeholder ?? '模型名称'}
            onChange={(e) => onChange(e.target.value)}
            className="font-mono text-xs"
          />
          <datalist id={listId}>
            {(field.options ?? MODEL_SUGGESTIONS).map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </>
      );
      break;
    case 'json':
      control = (
        <>
          <Textarea
            rows={field.rows ?? 4}
            value={strValue}
            placeholder={field.placeholder ?? '{ }'}
            onChange={(e) => {
              onChange(e.target.value);
              try {
                if (e.target.value.trim()) JSON.parse(e.target.value);
                setJsonError(null);
              } catch (err) {
                setJsonError(err instanceof Error ? err.message : 'JSON 格式错误');
              }
            }}
            className={cn('font-mono text-xs', jsonError && 'border-red-600')}
          />
          {jsonError ? <div className="text-[10px] text-red-400">JSON 格式错误：{jsonError}</div> : null}
        </>
      );
      break;
    case 'file':
      control = <FileField nodeId={nodeId} field={field} value={value} onChange={onChange} />;
      break;
    case 'slider':
      control = (
        <div className="flex h-8 items-center gap-2">
          <input
            type="range"
            min={field.min ?? 0}
            max={field.max ?? 100}
            step={field.step ?? 1}
            value={typeof value === 'number' ? value : Number(strValue) || 0}
            onChange={(e) => onChange(Number(e.target.value))}
            className="w-full accent-sky-500"
          />
          <span className="w-10 text-right font-mono text-[11px] text-zinc-300">{strValue || '0'}</span>
        </div>
      );
      break;
    default: // 'text' 及未知类型回退为普通输入框
      control = (
        <Input value={strValue} placeholder={field.placeholder} onChange={(e) => onChange(e.target.value)} />
      );
  }

  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium text-zinc-400" title={field.description}>
        {fieldLabel(field)}
      </label>
      {control}
    </div>
  );
}

/** 不在面板直接展示的配置键（由专门 UI 管理，如 Review 面板的 edited_prompt）。 */
const HIDDEN_KEYS: Record<string, string[]> = {
  prompt_optimizer: ['edited_prompt'],
};
/** 常用配置键（其余折叠进「高级设置」）。 */
const PRIMARY_KEYS: Record<string, string[]> = {
  prompt_optimizer: ['mode', 'rewrite_instruction', 'target_video_model'],
  video_generation: ['credential_id', 'model', 'resolution', 'duration', 'ratio'],
  llm: ['credential_id', 'model', 'system_prompt'],
  storyboard: ['credential_id', 'model', 'shot_count'],
};

export function PropertiesPanel() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const schemas = useWorkflowStore((s) => s.nodeSchemas);
  const updateNodeConfigValue = useWorkflowStore((s) => s.updateNodeConfigValue);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const selected = useMemo(() => nodes.filter((n) => n.selected), [nodes]);
  const node = selected.length === 1 ? selected[0] : null;
  const nodeType = node?.data.nodeType ?? '';
  const schema = node ? schemas[nodeType] : null;

  const hidden = HIDDEN_KEYS[nodeType] ?? [];
  const primary = PRIMARY_KEYS[nodeType] ?? null;
  const visibleFields = (schema?.config_schema ?? []).filter((f) => !hidden.includes(f.key));
  const primaryFields = primary ? visibleFields.filter((f) => primary.includes(f.key)) : visibleFields;
  const advancedFields = primary ? visibleFields.filter((f) => !primary.includes(f.key)) : [];

  const renderField = (field: ConfigField) =>
    node ? (
      <ConfigFieldRow
        key={field.key}
        nodeId={node.id}
        field={field}
        value={node.data.config[field.key]}
        onChange={(v) => updateNodeConfigValue(node.id, field.key, v)}
      />
    ) : null;

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l border-zinc-800 bg-zinc-900/60">
      <div className="flex h-10 items-center border-b border-zinc-800 px-3 text-xs font-semibold text-zinc-300">
        属性
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {!node || !schema ? (
          <div className="pt-6 text-center text-xs text-zinc-500">
            {selected.length > 1 ? '已选中多个节点' : '选中一个节点以编辑其配置'}
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-zinc-100">{nodeLabel(node.data.nodeType).name}</span>
                {schema.is_paid ? (
                  <span className="rounded bg-amber-900/70 px-1 text-[9px] font-semibold text-amber-300">付费</span>
                ) : null}
              </div>
              <div className="mt-0.5 font-mono text-[10px] text-zinc-500">
                {node.id} · v{schema.version}
              </div>
              {nodeLabel(node.data.nodeType).description ? (
                <p className="mt-1 text-[11px] text-zinc-500">{nodeLabel(node.data.nodeType).description}</p>
              ) : null}
            </div>

            {nodeType === 'prompt_optimizer' ? <PromptReview nodeId={node.id} /> : null}

            {primaryFields.map(renderField)}

            {advancedFields.length > 0 ? (
              <div className="rounded-md border border-zinc-800">
                <button
                  type="button"
                  onClick={() => setAdvancedOpen((v) => !v)}
                  className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium text-zinc-400 transition-colors hover:text-zinc-200"
                >
                  {advancedOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  高级设置
                  <span className="text-[10px] text-zinc-600">凭证 / 模型 / 温度等，一般无需改动</span>
                </button>
                {advancedOpen ? (
                  <div className="space-y-3 border-t border-zinc-800 p-2.5">
                    {advancedFields.map(renderField)}
                  </div>
                ) : null}
              </div>
            ) : null}

            {visibleFields.length === 0 ? (
              <div className="text-[11px] text-zinc-600">此节点没有可配置项。</div>
            ) : null}
          </div>
        )}
      </div>
    </aside>
  );
}
