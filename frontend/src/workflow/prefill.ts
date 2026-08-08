// 模板预填：把凭证/模型/视频参数/提示词/图片注入模板 JSON（快速开始与 File 菜单模板共用）。
// 只改 config 引用字段，绝不写入任何 secret（SPEC §4）。
import type { UploadResult, WorkflowJSON } from '../types';

export interface PrefillOptions {
  llmCredentialId?: string | null;
  llmModel?: string;
  videoCredentialId?: string | null;
  videoModel?: string;
  resolution?: string;
  duration?: number;
  ratio?: string;
  /** 依次填入各 prompt/text 空文本节点（三镜头=3 段、连续镜头=2 段、其余=1 段）。 */
  promptTexts?: string[];
  /** 图生视频：注入 image_input 节点的 file。 */
  imageFile?: UploadResult | null;
}

const LLM_NODE_TYPES = new Set(['prompt_optimizer', 'llm', 'storyboard']);

export function prefillWorkflow(data: WorkflowJSON, opts: PrefillOptions): WorkflowJSON {
  const cloned = structuredClone(data);
  const promptQueue = [...(opts.promptTexts ?? [])];

  for (const node of cloned.nodes) {
    const config = (node.config ?? {}) as Record<string, unknown>;
    node.config = config;

    if (node.type === 'video_generation') {
      if (opts.videoCredentialId) config.credential_id = opts.videoCredentialId;
      if (opts.videoModel) config.model = opts.videoModel;
      if (opts.resolution) config.resolution = opts.resolution;
      if (opts.duration !== undefined) config.duration = opts.duration;
      if (opts.ratio) config.ratio = opts.ratio;
    } else if (LLM_NODE_TYPES.has(node.type)) {
      if (opts.llmCredentialId) config.credential_id = opts.llmCredentialId;
      if (opts.llmModel) config.model = opts.llmModel;
    } else if (node.type === 'prompt' || node.type === 'text') {
      // 依次填充空文本节点：第 i 个空节点用 promptTexts[i]
      if (!config.text && promptQueue.length > 0) {
        const text = promptQueue.shift();
        if (text) config.text = text;
      }
    } else if (node.type === 'image_input' && opts.imageFile) {
      config.file = opts.imageFile;
    }
  }
  return cloned;
}

/** File 菜单模板的默认预填参数（需求 4）。 */
export const DEFAULT_LLM_MODEL = 'deepseek-v4-flash';
export const DEFAULT_VIDEO_MODEL = 'MiniMax-H3';
export const DEFAULT_RESOLUTION = '768P';
export const DEFAULT_DURATION = 6;
export const DEFAULT_RATIO = '16:9';

/** 同名工作流去重：文生视频 → 文生视频 2 → 文生视频 3 … */
export function uniqueName(base: string, existing: string[]): string {
  if (!existing.includes(base)) return base;
  let i = 2;
  while (existing.includes(`${base} ${i}`)) i += 1;
  return `${base} ${i}`;
}
