// 快速开始（需求 3）：选场景 → 输入提示词/图片 + 视频参数 + 选凭证模型 → 基于模板创建工作流。
import { Clapperboard, Film, Image as ImageIcon, KeyRound, ListVideo, Sparkles, Upload, Type } from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import * as api from '../api/resources';
import { ApiError } from '../api/client';
import { cn } from '../lib/utils';
import { nodeLabel, templateLabel } from '../nodes/labels';
import { useCredentialStore } from '../stores/credentialStore';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';
import type { Template, UploadResult } from '../types';
import {
  DEFAULT_DURATION,
  DEFAULT_LLM_MODEL,
  DEFAULT_RATIO,
  DEFAULT_RESOLUTION,
  DEFAULT_VIDEO_MODEL,
  prefillWorkflow,
  uniqueName,
} from '../workflow/prefill';
import { Button } from './ui/button';
import { Dialog } from './ui/dialog';
import { Input, Textarea } from './ui/input';
import { Select } from './ui/select';
import { toast } from './ui/toast';

type ScenarioId = 'text_to_video' | 'image_to_video' | 'last_frame_continue' | 'three_shot_movie' | 'story_to_storyboard';

interface PromptField {
  label: string;
  placeholder: string;
  optional?: boolean;
}

interface Scenario {
  id: ScenarioId;
  icon: ReactNode;
  needsImage: boolean;
  /** 按场景 1~3 段提示词输入（三镜头=3 段、连续镜头=2 段、其余=1 段）。 */
  prompts: PromptField[];
  hasVideo: boolean;
  hasLlm: boolean;
}

const SCENARIOS: Scenario[] = [
  {
    id: 'text_to_video',
    icon: <Type size={18} />,
    needsImage: false,
    prompts: [{
      label: '提示词',
      placeholder: '例如：一位穿着红色汉服的少女站在江南雨巷中，细雨飘落，青石板路反光，电影感，浅景深…',
    }],
    hasVideo: true,
    hasLlm: true,
  },
  {
    id: 'image_to_video',
    icon: <ImageIcon size={18} />,
    needsImage: true,
    prompts: [{
      label: '提示词（可选）',
      placeholder: '例如：镜头缓慢推近，微风吹动发丝，背景光斑虚化…',
      optional: true,
    }],
    hasVideo: true,
    hasLlm: false,
  },
  {
    id: 'last_frame_continue',
    icon: <Clapperboard size={18} />,
    needsImage: false,
    prompts: [
      {
        label: '第一段提示词',
        placeholder: '例如：赛博朋克都市夜景，霓虹灯下的雨夜街道，一位侦探撑伞走过…',
      },
      {
        label: '第二段提示词（续拍）',
        placeholder: '例如：侦探停下脚步，抬头看向霓虹招牌，镜头缓慢推近他的侧脸…',
      },
    ],
    hasVideo: true,
    hasLlm: true,
  },
  {
    id: 'three_shot_movie',
    icon: <Film size={18} />,
    needsImage: false,
    prompts: [
      { label: '镜头 1 提示词', placeholder: '例如：金色麦田，黄昏逆光，一位旅人骑马从远处驶来，史诗感…' },
      { label: '镜头 2 提示词', placeholder: '例如：特写马蹄踏过麦浪，尘土飞扬，慢镜头…' },
      { label: '镜头 3 提示词', placeholder: '例如：旅人在山脊上勒马回望，夕阳剪影，镜头拉远…' },
    ],
    hasVideo: true,
    hasLlm: true,
  },
  {
    id: 'story_to_storyboard',
    icon: <ListVideo size={18} />,
    needsImage: false,
    prompts: [{
      label: '故事文本',
      placeholder: '例如：深夜便利店，值班店员发现冰柜里有一封十年前写给自己的信…',
    }],
    hasVideo: false,
    hasLlm: true,
  },
];

const RESOLUTIONS = ['768P', '2K'];
const RATIOS = ['16:9', '9:16', '1:1', '4:3', '3:4', '21:9', 'adaptive'];

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium text-zinc-400">{label}</label>
      {children}
    </div>
  );
}

export function QuickStartDialog() {
  const open = useUIStore((s) => s.quickStartOpen);
  const setOpen = useUIStore((s) => s.setQuickStartOpen);
  const setCredentialsOpen = useUIStore((s) => s.setCredentialsOpen);
  const credentials = useCredentialStore((s) => s.credentials);
  const loadAll = useCredentialStore((s) => s.loadAll);
  const loadWorkflow = useWorkflowStore((s) => s.loadWorkflow);

  const [templates, setTemplates] = useState<Template[]>([]);
  const [scenarioId, setScenarioId] = useState<ScenarioId>('text_to_video');
  const [promptTexts, setPromptTexts] = useState<string[]>(['']);
  const [file, setFile] = useState<UploadResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [resolution, setResolution] = useState(DEFAULT_RESOLUTION);
  const [duration, setDuration] = useState(DEFAULT_DURATION);
  const [ratio, setRatio] = useState(DEFAULT_RATIO);
  const [llmCredId, setLlmCredId] = useState('');
  const [llmModel, setLlmModel] = useState(DEFAULT_LLM_MODEL);
  const [videoCredId, setVideoCredId] = useState('');
  const [videoModel, setVideoModel] = useState(DEFAULT_VIDEO_MODEL);
  const [creating, setCreating] = useState(false);

  const scenario = SCENARIOS.find((s) => s.id === scenarioId)!;

  // 切换场景时重置提示词输入（段数随场景变化：1/2/3 段）
  useEffect(() => {
    setPromptTexts(Array(scenario.prompts.length).fill(''));
  }, [scenarioId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    void loadAll();
    api.getTemplates().then((r) => setTemplates(r.data)).catch(() => setTemplates([]));
  }, [open, loadAll]);

  // 默认选中 is_default 凭证（无默认则取第一个）。
  useEffect(() => {
    if (!open) return;
    const pick = (kind: string) => {
      const list = credentials.filter((c) => c.kind === kind);
      return (list.find((c) => c.is_default) ?? list[0])?.id ?? '';
    };
    setLlmCredId((v) => v || pick('llm'));
    setVideoCredId((v) => v || pick('video'));
  }, [open, credentials]);

  const llmCreds = useMemo(() => credentials.filter((c) => c.kind === 'llm'), [credentials]);
  const videoCreds = useMemo(() => credentials.filter((c) => c.kind === 'video'), [credentials]);

  const missingLlm = scenario.hasLlm && llmCreds.length === 0;
  const missingVideo = scenario.hasVideo && videoCreds.length === 0;
  const blocked = missingLlm || missingVideo;

  const doUpload = async (f: File) => {
    setUploading(true);
    try {
      const { data } = await api.uploadFile(f);
      setFile(data);
      toast.success('图片已上传', f.name);
    } catch (e) {
      toast.error('上传失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setUploading(false);
    }
  };

  const create = async () => {
    const tpl = templates.find((t) => t.id === scenario.id);
    const data = tpl?.data ?? tpl?.workflow;
    if (!data) {
      toast.error('模板不可用', templateLabel(scenario.id, scenario.id).name);
      return;
    }
    if (scenario.needsImage && !file) {
      toast.error('请先上传图片');
      return;
    }
    // 每段提示词逐个校验（可选段除外），避免空提示词产生无效付费视频
    for (let i = 0; i < scenario.prompts.length; i++) {
      const field = scenario.prompts[i];
      if (!field.optional && !(promptTexts[i] ?? '').trim()) {
        toast.error(`请填写${field.label}`, '所有提示词填好再创建，避免空提示词产生无效视频');
        return;
      }
    }
    setCreating(true);
    try {
      const prefilled = prefillWorkflow(data, {
        llmCredentialId: llmCredId || null,
        llmModel,
        videoCredentialId: videoCredId || null,
        videoModel,
        resolution,
        duration,
        ratio,
        promptTexts: promptTexts.map((t) => t.trim()),
        imageFile: file,
      });
      const label = templateLabel(scenario.id, tpl?.name ?? scenario.id);
      const { data: existing } = await api.listWorkflows();
      const name = uniqueName(label.name, existing.map((w) => w.name));
      prefilled.name = name;
      const { data: record } = await api.createWorkflow(name, prefilled);
      loadWorkflow(record);
      toast.success('工作流已创建', '画布已就绪，点击右上角「运行」开始');
      setOpen(false);
    } catch (e) {
      toast.error('创建失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      title={
        <span className="flex items-center gap-1.5">
          <Sparkles size={15} className="text-sky-400" /> 快速开始
        </span>
      }
      description="选择一个场景，填入提示词和参数，即刻生成可运行的工作流。"
      className="max-w-3xl"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button size="sm" disabled={creating || blocked || uploading} onClick={() => void create()}>
            <Sparkles size={13} /> {creating ? '创建中…' : '创建工作流'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {/* 场景选择 */}
        <div className="grid grid-cols-5 gap-2">
          {SCENARIOS.map((s) => {
            const label = templateLabel(s.id, s.id);
            const active = s.id === scenarioId;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => setScenarioId(s.id)}
                className={cn(
                  'flex flex-col items-start gap-1.5 rounded-lg border p-2.5 text-left transition-colors',
                  active
                    ? 'border-sky-600 bg-sky-950/40 ring-1 ring-sky-700'
                    : 'border-zinc-800 bg-zinc-900 hover:border-zinc-600',
                )}
              >
                <span className={active ? 'text-sky-400' : 'text-zinc-500'}>{s.icon}</span>
                <span className="text-xs font-medium text-zinc-100">{label.name}</span>
                <span className="text-[10px] leading-tight text-zinc-500">{label.description}</span>
              </button>
            );
          })}
        </div>

        {blocked ? (
          <div className="flex items-center justify-between gap-3 rounded-md border border-amber-800/60 bg-amber-950/40 px-3 py-2">
            <span className="text-xs text-amber-300">
              还没有可用的{missingLlm ? ' LLM ' : ''}{missingLlm && missingVideo ? '和' : ''}{missingVideo ? '视频' : ''}
              凭证，请先去配置。
            </span>
            <Button
              variant="secondary"
              size="xs"
              onClick={() => {
                setOpen(false);
                setCredentialsOpen(true);
              }}
            >
              <KeyRound size={11} /> 去配置凭证
            </Button>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-4">
          {/* 左列：提示词 / 图片 */}
          <div className="space-y-3">
            {scenario.needsImage ? (
              <Field label="首帧图片">
                <div className="space-y-1.5">
                  <label
                    className={cn(
                      'flex h-28 cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed text-xs',
                      file ? 'border-zinc-700' : 'border-zinc-600 hover:border-zinc-400 hover:bg-zinc-800/50',
                      uploading && 'opacity-50',
                    )}
                  >
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      disabled={uploading}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void doUpload(f);
                        e.target.value = '';
                      }}
                    />
                    {file ? (
                      <img src={file.url} alt="首帧" className="h-full w-full rounded-md object-contain" />
                    ) : (
                      <>
                        <Upload size={16} className="text-zinc-500" />
                        <span className="text-zinc-400">{uploading ? '上传中…' : '点击上传图片'}</span>
                      </>
                    )}
                  </label>
                </div>
              </Field>
            ) : null}
            {scenario.prompts.map((field, i) => (
              <Field key={field.label} label={field.label}>
                <Textarea
                  rows={scenario.prompts.length > 1 ? 3 : scenario.needsImage ? 4 : 7}
                  value={promptTexts[i] ?? ''}
                  onChange={(e) =>
                    setPromptTexts((prev) => prev.map((t, j) => (j === i ? e.target.value : t)))
                  }
                  placeholder={field.placeholder}
                  className="text-sm leading-relaxed"
                />
              </Field>
            ))}
          </div>

          {/* 右列：参数与模型 */}
          <div className="space-y-3">
            {scenario.hasVideo ? (
              <>
                <div className="grid grid-cols-3 gap-2">
                  <Field label="分辨率">
                    <Select value={resolution} onChange={(e) => setResolution(e.target.value)}>
                      {RESOLUTIONS.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="时长（秒）">
                    <Input
                      type="number"
                      min={4}
                      max={15}
                      value={duration}
                      onChange={(e) => setDuration(Math.max(4, Math.min(15, Number(e.target.value) || DEFAULT_DURATION)))}
                    />
                  </Field>
                  <Field label="画面比例">
                    <Select value={ratio} onChange={(e) => setRatio(e.target.value)}>
                      {RATIOS.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <Field label="视频凭证">
                  <Select value={videoCredId} onChange={(e) => setVideoCredId(e.target.value)}>
                    <option value="">— 未选择 —</option>
                    {videoCreds.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}（{c.provider}）{c.is_default ? ' · 默认' : ''}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="视频模型">
                  <Input value={videoModel} onChange={(e) => setVideoModel(e.target.value)} className="font-mono text-xs" />
                </Field>
              </>
            ) : null}
            {scenario.hasLlm ? (
              <>
                <Field label="LLM 凭证">
                  <Select value={llmCredId} onChange={(e) => setLlmCredId(e.target.value)}>
                    <option value="">— 未选择 —</option>
                    {llmCreds.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}（{c.provider}）{c.is_default ? ' · 默认' : ''}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="LLM 模型">
                  <Input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} className="font-mono text-xs" />
                </Field>
              </>
            ) : null}
            <p className="text-[10px] leading-relaxed text-zinc-600">
              将基于「{templateLabel(scenario.id, scenario.id).name}」模板创建：
              {templates.find((t) => t.id === scenario.id)?.data?.nodes.map((n) => nodeLabel(n.type).name).join(' → ') ??
                '…'}
            </p>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
