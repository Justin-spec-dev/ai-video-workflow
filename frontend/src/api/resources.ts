// REST resources, one function per SPEC §6 endpoint. All paths carry the /api prefix.
import { http } from './client';
import type {
  CostEstimate,
  Credential,
  CredentialCreate,
  CredentialUpdate,
  NodeSchema,
  ProviderInfo,
  ProviderTask,
  RunDetail,
  RunRequest,
  Template,
  TestConnectionResult,
  UploadResult,
  WorkflowJSON,
  WorkflowRecord,
  WorkflowRun,
  WorkflowSummary,
} from '../types';

// ---- Nodes / templates / providers ----
export const getNodes = () => http.get<NodeSchema[]>('/api/nodes');
export const getTemplates = () => http.get<Template[]>('/api/templates');
export const getProviders = () => http.get<ProviderInfo[]>('/api/providers');
export const getHealth = () => http.get<{ status: string }>('/api/health');

// ---- Workflows ----
export const listWorkflows = () => http.get<WorkflowSummary[]>('/api/workflows');
export const createWorkflow = (name: string, data?: WorkflowJSON) =>
  http.post<WorkflowRecord>('/api/workflows', { name, data });
export const getWorkflow = (id: string) => http.get<WorkflowRecord>(`/api/workflows/${id}`);
export const updateWorkflow = (id: string, payload: { name?: string; data?: WorkflowJSON }) =>
  http.put<WorkflowRecord>(`/api/workflows/${id}`, payload);
export const deleteWorkflow = (id: string) => http.delete<void>(`/api/workflows/${id}`);
export const duplicateWorkflow = (id: string) =>
  http.post<WorkflowRecord>(`/api/workflows/${id}/duplicate`);
export const estimateWorkflow = (id: string) =>
  http.post<CostEstimate>(`/api/workflows/${id}/estimate`);
export const runWorkflow = (id: string, body: RunRequest) =>
  http.post<WorkflowRun | { run_id: string; status: 'waiting_confirmation'; estimate: CostEstimate }>(
    `/api/workflows/${id}/run`,
    body,
  );

// ---- Runs ----
export const listRuns = (workflowId?: string) =>
  http.get<WorkflowRun[]>(`/api/runs${workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : ''}`);
export const getRun = (id: string) => http.get<RunDetail>(`/api/runs/${id}`);
export const confirmRun = (id: string) => http.post<WorkflowRun>(`/api/runs/${id}/confirm`);
export const stopRun = (id: string) => http.post<WorkflowRun>(`/api/runs/${id}/stop`);
export const resumeRun = (id: string) => http.post<WorkflowRun>(`/api/runs/${id}/resume`);

// ---- Per-node actions ----
export const runNode = (workflowId: string, nodeId: string, downstream: boolean) =>
  http.post<WorkflowRun>(`/api/workflows/${workflowId}/nodes/${nodeId}/run`, { downstream });
export const clearNodeCache = (workflowId: string, nodeId: string) =>
  http.delete<void>(`/api/workflows/${workflowId}/nodes/${nodeId}/cache`);

// ---- Tasks ----
export const listTasks = (params?: { workflow_id?: string; status?: string }) => {
  const qs = new URLSearchParams();
  if (params?.workflow_id) qs.set('workflow_id', params.workflow_id);
  if (params?.status) qs.set('status', params.status);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return http.get<ProviderTask[]>(`/api/tasks${suffix}`);
};
export const getTask = (id: string) => http.get<ProviderTask>(`/api/tasks/${id}`);
export const refreshTask = (id: string) => http.post<ProviderTask>(`/api/tasks/${id}/refresh`);
export const cancelTask = (id: string) => http.post<ProviderTask>(`/api/tasks/${id}/cancel`);

// ---- Credentials ----
export const listCredentials = (kind?: string) =>
  http.get<Credential[]>(`/api/credentials${kind ? `?kind=${encodeURIComponent(kind)}` : ''}`);
export const createCredential = (body: CredentialCreate) => http.post<Credential>('/api/credentials', body);
export const updateCredential = (id: string, body: CredentialUpdate) =>
  http.put<Credential>(`/api/credentials/${id}`, body);
export const deleteCredential = (id: string) => http.delete<void>(`/api/credentials/${id}`);
export const testCredential = (id: string) =>
  http.post<TestConnectionResult>(`/api/credentials/${id}/test`);

// ---- Files / settings ----
export const uploadFile = (file: File) => http.upload<UploadResult>('/api/files/upload', file);
export const getSettings = () => http.get<Record<string, unknown>>('/api/settings');
export const putSettings = (body: Record<string, unknown>) =>
  http.put<Record<string, unknown>>('/api/settings', body);
