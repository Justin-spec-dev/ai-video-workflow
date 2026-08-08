// credentialStore (SPEC §10): credential list (masked only) + provider metadata.
import { create } from 'zustand';
import * as api from '../api/resources';
import type { Credential, ProviderInfo } from '../types';

interface CredentialStoreState {
  credentials: Credential[];
  providers: ProviderInfo[];
  loaded: boolean;
  loadAll: () => Promise<void>;
  byKind: (kind: string) => Credential[];
}

export const useCredentialStore = create<CredentialStoreState>((set, get) => ({
  credentials: [],
  providers: [],
  loaded: false,

  loadAll: async () => {
    const [creds, providers] = await Promise.all([
      api.listCredentials().catch(() => ({ data: [] as Credential[], status: 0 })),
      api.getProviders().catch(() => ({ data: [] as ProviderInfo[], status: 0 })),
    ]);
    set({ credentials: creds.data, providers: providers.data, loaded: true });
  },

  byKind: (kind) => get().credentials.filter((c) => c.kind === kind),
}));
