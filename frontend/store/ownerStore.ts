import { create } from 'zustand';
import api from '../services/api';

// Owner layer: one account above super admins decides which internal tools the other super admins can see.
type State = {
  loaded: boolean;
  isOwner: boolean;
  visibility: Record<string, boolean>;
  load: () => Promise<void>;
  canSee: (key?: string) => boolean;
  reset: () => void;
};

let inflight: Promise<void> | null = null;

export const useOwnerStore = create<State>((set, get) => ({
  loaded: false,
  isOwner: false,
  visibility: {},
  load: async () => {
    if (inflight) return inflight;
    inflight = api.get('/owner/visibility', { timeout: 15000 })
      .then(r => set({ loaded: true, isOwner: !!r.data.is_owner, visibility: r.data.visibility || {} }))
      .catch(() => set({ loaded: true }))
      .finally(() => { inflight = null; });
    return inflight;
  },
  canSee: (key) => {
    if (!key) return true;
    const { isOwner, visibility, loaded } = get();
    if (isOwner) return true;
    if (!loaded) return false;
    return visibility[key] !== false;
  },
  reset: () => set({ loaded: false, isOwner: false, visibility: {} }),
}));
