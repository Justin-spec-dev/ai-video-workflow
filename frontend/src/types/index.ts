// Types mirroring docs/SPEC.md — the authoritative contract.

// ---- §2 PortType ----
export type PortTypeBase =
  | 'TEXT'
  | 'PROMPT'
  | 'IMAGE'
  | 'VIDEO'
  | 'AUDIO'
  | 'JSON'
  | 'NUMBER'
  | 'BOOLEAN'
  | 'FILE';

/** Port type, e.g. "TEXT" or array form "IMAGE[]". */
export type PortType = string;

// ---- §3 Node Schema ----
export interface PortDef {
  key: string;
  name: string;
  type: PortType;
  required?: boolean;
  multiple?: boolean;
  description?: string;
}

export type ConfigFieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'boolean'
  | 'select'
  | 'credential'
  | 'model'
  | 'json'
  | 'file'
  | 'slider';

export interface ConfigField {
  key: string;
  name: string;
  type: ConfigFieldType;
  default?: unknown;
  placeholder?: string;
  description?: string;
  rows?: number;
  options?: string[];
  provider_kind?: 'llm' | 'video' | string;
  min?: number;
  max?: number;
  step?: number;
}

export type NodeCategory =
  | 'Input'
  | 'Text'
  | 'Context'
  | 'AI'
  | 'Image'
  | 'Video'
  | 'Logic'
  | 'Utility'
  | 'Output'
  | string;

export interface NodeSchema {
  type: string;
  name: string;
  version: string;
  category: NodeCategory;
  description: string;
  is_paid: boolean;
  inputs: PortDef[];
  outputs: PortDef[];
  config_schema: ConfigField[];
}

// ---- §3 node output values ----
export interface MediaValue {
  path: string;
  url: string;
  width?: number;
  height?: number;
  duration?: number;
  filename?: string;
}

export type NodeOutputs = Record<string, unknown>;

// ---- §4 Workflow JSON ----
export interface WorkflowNodeJSON {
  id: string;
  type: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;
}

export interface WorkflowEdgeJSON {
  id: string;
  source: string;
  source_handle: string;
  target: string;
  target_handle: string;
}

export interface Viewport {
  x: number;
  y: number;
  zoom: number;
}

export interface WorkflowJSON {
  version: number;
  name: string;
  nodes: WorkflowNodeJSON[];
  edges: WorkflowEdgeJSON[];
  viewport: Viewport;
}

export interface WorkflowSummary {
  id: string;
  name: string;
  updated_at: string;
}

export interface WorkflowRecord {
  id: string;
  name: string;
  data: WorkflowJSON;
  created_at?: string;
  updated_at?: string;
}

// ---- Node / run status (§5.5 state machine) ----
export type NodeStatus =
  | 'IDLE'
  | 'QUEUED'
  | 'WAITING_CONFIRMATION'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'CACHED'
  | 'CANCELLED';

export type RunStatus =
  | 'running'
  | 'success'
  | 'failed'
  | 'cancelled'
  | 'waiting_confirmation';

// ---- §6 resources ----
export interface CostEstimate {
  paid_node_count: number;
  estimated_api_calls: number;
  estimated_video_seconds: number;
  estimated_cost: number | null;
  currency: string;
  notes: string[];
}

export interface RunRequest {
  confirm_paid: boolean;
  resume_from_run_id?: string;
  run_from_node_id?: string;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: RunStatus;
  trigger?: string;
  cost_estimate?: CostEstimate | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface NodeRun {
  id: string;
  run_id: string;
  workflow_id: string;
  node_id: string;
  node_type: string;
  status: NodeStatus;
  inputs?: Record<string, unknown> | null;
  outputs?: NodeOutputs | null;
  error?: string | null;
  provider?: string | null;
  model?: string | null;
  task_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface RunDetail extends WorkflowRun {
  node_runs: NodeRun[];
}

export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface ProviderTask {
  id: string;
  run_id: string;
  workflow_id: string;
  node_id: string;
  provider: string;
  model?: string | null;
  credential_id?: string | null;
  remote_task_id?: string | null;
  status: TaskStatus | string;
  remote_status?: Record<string, unknown> | null;
  output?: MediaValue | Record<string, unknown> | null;
  error?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ProviderInfo {
  name: string;
  display_name: string;
  kind: 'llm' | 'video' | string;
  config_schema?: ConfigField[];
}

export interface Credential {
  id: string;
  name: string;
  kind: 'llm' | 'video' | string;
  provider: string;
  base_url?: string | null;
  is_default: boolean;
  masked_secret: string;
  created_at?: string;
}

export interface CredentialCreate {
  name: string;
  kind: string;
  provider: string;
  base_url?: string | null;
  api_key: string;
  is_default?: boolean;
}

export interface CredentialUpdate {
  name?: string;
  provider?: string;
  base_url?: string | null;
  /** Empty/omitted means unchanged (SPEC §10). */
  api_key?: string;
  is_default?: boolean;
}

export interface TestConnectionResult {
  ok: boolean;
  message: string;
}

export interface Template {
  id?: string;
  name: string;
  description?: string;
  data?: WorkflowJSON;
  workflow?: WorkflowJSON;
}

export interface UploadResult {
  path: string;
  url: string;
  width?: number;
  height?: number;
}

// ---- §7 WebSocket events ----
export interface WSEvent<T = Record<string, unknown>> {
  event: string;
  ts: number;
  payload: T;
}

export interface NodeEventPayload {
  run_id: string;
  node_id: string;
  node_type: string;
  error?: string;
  outputs?: NodeOutputs;
}

export interface TaskEventPayload {
  task_id: string;
  node_id: string;
  remote_status?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface LogEventPayload {
  run_id: string;
  node_id?: string;
  level: string;
  message: string;
}

export interface LogEntry {
  ts: number;
  run_id?: string;
  node_id?: string;
  level: string;
  message: string;
}
