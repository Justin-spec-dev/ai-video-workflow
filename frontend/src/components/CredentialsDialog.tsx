// 凭证管理（SPEC §5.4/§10）：LLM/视频分组，添加/编辑/删除/测试连接/设为默认。
// secret 绝不回显 —— 编辑时留空表示不变。
import { Check, KeyRound, Pencil, Plus, Star, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import * as api from '../api/resources';
import { ApiError } from '../api/client';
import { cn } from '../lib/utils';
import { useCredentialStore } from '../stores/credentialStore';
import { useUIStore } from '../stores/uiStore';
import type { Credential } from '../types';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Dialog } from './ui/dialog';
import { Input } from './ui/input';
import { Select } from './ui/select';
import { toast } from './ui/toast';

interface FormState {
  mode: 'add' | 'edit';
  id?: string;
  kind: string;
  name: string;
  provider: string;
  base_url: string;
  secret: string;
  is_default: boolean;
}

const KIND_LABELS: Record<string, string> = { llm: 'LLM', video: '视频' };

export function CredentialsDialog() {
  const open = useUIStore((s) => s.credentialsOpen);
  const setOpen = useUIStore((s) => s.setCredentialsOpen);
  const credentials = useCredentialStore((s) => s.credentials);
  const providers = useCredentialStore((s) => s.providers);
  const loadAll = useCredentialStore((s) => s.loadAll);

  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string }>>({});

  useEffect(() => {
    if (open) void loadAll();
  }, [open, loadAll]);

  const providersOfKind = (kind: string) => providers.filter((p) => p.kind === kind);

  const startAdd = (kind: string) => {
    const first = providersOfKind(kind)[0];
    setForm({
      mode: 'add',
      kind,
      name: '',
      provider: first?.name ?? '',
      base_url: '',
      secret: '',
      is_default: false,
    });
  };

  const startEdit = (c: Credential) => {
    setForm({
      mode: 'edit',
      id: c.id,
      kind: c.kind,
      name: c.name,
      provider: c.provider,
      base_url: c.base_url ?? '',
      secret: '', // 留空 = 不变（§10）
      is_default: c.is_default,
    });
  };

  const save = async () => {
    if (!form) return;
    if (!form.name.trim() || !form.provider) {
      toast.error('名称和提供商为必填项');
      return;
    }
    if (form.mode === 'add' && !form.secret) {
      toast.error('请填写密钥');
      return;
    }
    setSaving(true);
    try {
      if (form.mode === 'add') {
        await api.createCredential({
          name: form.name.trim(),
          kind: form.kind,
          provider: form.provider,
          base_url: form.base_url.trim() || null,
          api_key: form.secret,
          is_default: form.is_default,
        });
        toast.success('凭证已添加');
      } else if (form.id) {
        await api.updateCredential(form.id, {
          name: form.name.trim(),
          provider: form.provider,
          base_url: form.base_url.trim() || null,
          ...(form.secret ? { api_key: form.secret } : {}), // 不变则不传
          is_default: form.is_default,
        });
        toast.success('凭证已更新');
      }
      setForm(null);
      await loadAll();
    } catch (e) {
      toast.error('保存失败', e instanceof ApiError ? e.detail : undefined);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (c: Credential) => {
    if (!window.confirm(`确定删除凭证「${c.name}」？`)) return;
    try {
      await api.deleteCredential(c.id);
      toast.success('凭证已删除');
      await loadAll();
    } catch (e) {
      toast.error('删除失败', e instanceof ApiError ? e.detail : undefined);
    }
  };

  const test = async (c: Credential) => {
    setTestResults((r) => ({ ...r, [c.id]: { ok: false, message: '测试中…' } }));
    try {
      const { data } = await api.testCredential(c.id);
      setTestResults((r) => ({ ...r, [c.id]: { ok: data.ok, message: data.message } }));
    } catch (e) {
      setTestResults((r) => ({
        ...r,
        [c.id]: { ok: false, message: e instanceof ApiError ? e.detail : '测试失败' },
      }));
    }
  };

  const setDefault = async (c: Credential) => {
    try {
      await api.updateCredential(c.id, { is_default: true });
      await loadAll();
      toast.success(`「${c.name}」已设为默认${KIND_LABELS[c.kind] ?? c.kind}凭证`);
    } catch (e) {
      toast.error('设置失败', e instanceof ApiError ? e.detail : undefined);
    }
  };

  const renderGroup = (kind: string, label: string) => {
    const items = credentials.filter((c) => c.kind === kind);
    return (
      <section>
        <div className="mb-1.5 flex items-center justify-between">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{label}</h3>
          <Button variant="secondary" size="xs" onClick={() => startAdd(kind)}>
            <Plus size={11} /> 添加
          </Button>
        </div>
        {items.length === 0 ? (
          <div className="rounded border border-dashed border-zinc-800 px-3 py-2 text-[11px] text-zinc-600">
            暂无{label}凭证。
          </div>
        ) : (
          <div className="space-y-1">
            {items.map((c) => {
              const result = testResults[c.id];
              return (
                <div key={c.id} className="rounded border border-zinc-800 bg-zinc-900 px-2.5 py-1.5">
                  <div className="flex items-center gap-2">
                    <KeyRound size={13} className="shrink-0 text-zinc-500" />
                    <span className="min-w-0 flex-1 truncate text-xs font-medium text-zinc-100">{c.name}</span>
                    <span className="text-[10px] text-zinc-500">{c.provider}</span>
                    <span className="font-mono text-[10px] text-zinc-500">{c.masked_secret}</span>
                    {c.is_default ? <Badge variant="success">默认</Badge> : null}
                    <div className="flex shrink-0 gap-0.5">
                      <Button variant="ghost" size="xs" title="测试连接" onClick={() => void test(c)}>
                        <Check size={11} /> 测试
                      </Button>
                      {!c.is_default ? (
                        <Button variant="ghost" size="xs" title="设为默认" onClick={() => void setDefault(c)}>
                          <Star size={11} />
                        </Button>
                      ) : null}
                      <Button variant="ghost" size="xs" title="编辑" onClick={() => startEdit(c)}>
                        <Pencil size={11} />
                      </Button>
                      <Button variant="ghost" size="xs" title="删除" onClick={() => void remove(c)}>
                        <Trash2 size={11} className="text-red-400" />
                      </Button>
                    </div>
                  </div>
                  {result ? (
                    <div className={cn('mt-1 text-[11px]', result.ok ? 'text-emerald-400' : 'text-red-400')}>
                      {result.ok ? '✓ ' : '✕ '}
                      {result.message}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </section>
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) setForm(null);
      }}
      title="凭证管理"
      description="密钥在服务端加密存储，此处只显示脱敏后的密钥。"
      className="max-w-2xl"
    >
      {form ? (
        <div className="space-y-3">
          <h3 className="text-xs font-semibold text-zinc-200">
            {form.mode === 'add'
              ? `添加${KIND_LABELS[form.kind] ?? form.kind}凭证`
              : `编辑「${form.name}」`}
          </h3>
          <div>
            <label className="mb-1 block text-[11px] text-zinc-400">名称</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-zinc-400">提供商</label>
            <Select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
              {providersOfKind(form.kind).length === 0 ? (
                <option value={form.provider}>{form.provider || '—'}</option>
              ) : (
                providersOfKind(form.kind).map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.display_name}
                  </option>
                ))
              )}
            </Select>
          </div>
          {(form.kind === 'llm' || form.base_url) && (
            <div>
              <label className="mb-1 block text-[11px] text-zinc-400">Base URL</label>
              <Input
                value={form.base_url}
                placeholder="https://api.openai.com/v1"
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                className="font-mono text-xs"
              />
            </div>
          )}
          <div>
            <label className="mb-1 block text-[11px] text-zinc-400">
              密钥 {form.mode === 'edit' ? <span className="text-zinc-600">（留空表示不修改）</span> : null}
            </label>
            <Input
              type="password"
              value={form.secret}
              placeholder={form.mode === 'edit' ? '••••••••' : 'sk-…'}
              onChange={(e) => setForm({ ...form, secret: e.target.value })}
              className="font-mono text-xs"
              autoComplete="new-password"
            />
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-zinc-300">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              className="h-3.5 w-3.5 accent-sky-500"
            />
            设为默认{KIND_LABELS[form.kind] ?? form.kind}凭证
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={() => setForm(null)}>
              返回
            </Button>
            <Button size="sm" disabled={saving} onClick={() => void save()}>
              {saving ? '保存中…' : form.mode === 'add' ? '添加凭证' : '保存修改'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {renderGroup('llm', 'LLM')}
          {renderGroup('video', '视频')}
        </div>
      )}
    </Dialog>
  );
}
