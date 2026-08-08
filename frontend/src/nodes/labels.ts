// 展示层中文映射：后端 schema 契约保持英文（type/name/description），UI 一律走这里的映射。
import type { ConfigField, NodeStatus } from '../types';

// ---- 节点类型 → 中文名/描述（对应 SPEC §5.2 节点清单）----
export interface NodeLabel {
  name: string;
  description: string;
}

export const NODE_LABELS: Record<string, NodeLabel> = {
  prompt: { name: '提示词', description: '多行提示词，支持 {{var}} 模板变量' },
  text: { name: '文本', description: '纯文本输入' },
  combine_prompt: { name: '组合提示词', description: '按模板组合角色/场景/动作/镜头' },
  variables: { name: '变量', description: 'key=value 变量列表，注入执行上下文' },
  character_context: { name: '角色设定', description: '姓名/外貌/服装/性格等角色一致性上下文' },
  scene_context: { name: '场景设定', description: '地点/时间/天气/环境等场景上下文' },
  style_context: { name: '风格设定', description: '画面风格/镜头语言/调色/光线等' },
  llm: { name: 'LLM', description: 'OpenAI 兼容大模型调用' },
  prompt_optimizer: { name: '提示词优化器', description: '用 LLM 优化/扩写视频提示词' },
  storyboard: { name: '故事分镜', description: '用 LLM 把故事拆成镜头列表' },
  json_parser: { name: 'JSON 解析', description: '用 jsonpath 子集提取字段' },
  image_input: { name: '图片输入', description: '上传图片作为首帧/参考图' },
  video_generation: { name: '视频生成', description: '调用视频生成模型（付费）' },
  last_frame: { name: '尾帧提取', description: '提取视频最后一帧作为图片' },
  frame_extract: { name: '抽帧', description: '按首帧/尾帧/时间点/百分比抽帧' },
  video_preview: { name: '视频预览', description: '预览视频（透传）' },
  video_merge: { name: '视频合并', description: '把多段视频拼接为一个' },
  save_file: { name: '保存文件', description: '把视频/图片/文本/JSON 保存到目录' },
};

export function nodeLabel(type: string): NodeLabel {
  return NODE_LABELS[type] ?? { name: type, description: '' };
}

// ---- 分类名 ----
export const CATEGORY_LABELS: Record<string, string> = {
  Input: '输入',
  Text: '文本',
  Context: '上下文',
  AI: 'AI',
  Image: '图像',
  Video: '视频',
  Logic: '逻辑',
  Utility: '工具',
  Output: '输出',
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

// ---- 节点状态（图标+文字，不只靠颜色）----
export const STATUS_LABELS: Record<NodeStatus, string> = {
  IDLE: '空闲',
  QUEUED: '排队中',
  WAITING_CONFIRMATION: '待确认',
  RUNNING: '运行中',
  SUCCESS: '成功',
  FAILED: '失败',
  CACHED: '缓存',
  CANCELLED: '已取消',
};

export function statusLabel(status: NodeStatus): string {
  return STATUS_LABELS[status] ?? status;
}

// ---- 运行 / 任务状态 ----
export const RUN_STATUS_LABELS: Record<string, string> = {
  running: '运行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
  waiting_confirmation: '待确认',
};

export const TASK_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  succeeded: '成功',
  failed: '失败',
  cancelled: '已取消',
};

export function runStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? status;
}

export function taskStatusLabel(status: string): string {
  return TASK_STATUS_LABELS[status] ?? status;
}

// ---- 配置字段 key → 中文标签（通用键优先，缺失回退后端 name）----
export const FIELD_LABELS: Record<string, string> = {
  text: '文本',
  template: '模板',
  entries: '变量列表',
  provider: '提供商',
  credential_id: '凭证',
  model: '模型',
  base_url: 'Base URL',
  temperature: '温度',
  system_prompt: '系统提示词',
  max_tokens: '最大 Token 数',
  mode: '模式',
  rewrite_instruction: '改写指令',
  target_video_model: '目标视频模型',
  edited_prompt: '编辑后的提示词',
  shot_count: '镜头数量',
  jsonpath: 'JSONPath',
  file: '文件',
  resolution: '分辨率',
  duration: '时长（秒）',
  ratio: '画面比例',
  retry_count: '重试次数',
  poll_interval: '轮询间隔（秒）',
  timeout: '超时（秒）',
  timestamp: '时间点（秒）',
  percentage: '百分比位置',
  reencode: '重新编码',
  directory: '目录',
  filename: '文件名',
  overwrite: '覆盖策略',
  name: '姓名',
  age: '年龄',
  gender: '性别',
  appearance: '外貌',
  hairstyle: '发型',
  clothing: '服装',
  personality: '性格',
  must_keep: '必须保持的特征',
  location: '地点',
  time: '时间',
  weather: '天气',
  environment: '环境',
  layout: '空间布局',
  persistent_objects: '持续出现的物体',
  visual_style: '画面风格',
  camera_language: '镜头语言',
  color_grading: '调色',
  lighting: '光线',
  aspect_ratio: '宽高比',
  film_texture: '胶片质感',
};

export function fieldLabel(field: ConfigField): string {
  return FIELD_LABELS[field.key] ?? field.name;
}

// ---- 内置模板（SPEC §8）----
export const TEMPLATE_LABELS: Record<string, NodeLabel> = {
  text_to_video: { name: '文生视频', description: '提示词 → 优化 → 生成视频' },
  image_to_video: { name: '图生视频', description: '上传图片作为首帧生成视频' },
  last_frame_continue: { name: '连续镜头', description: '尾帧续拍下一段视频' },
  three_shot_movie: { name: '三镜头短片', description: '三条生成链合并成片' },
  story_to_storyboard: { name: '故事分镜', description: '故事文本 → LLM → 分镜列表' },
};

export function templateLabel(id: string | undefined, fallback: string): NodeLabel {
  if (id && TEMPLATE_LABELS[id]) return TEMPLATE_LABELS[id];
  return { name: fallback, description: '' };
}
