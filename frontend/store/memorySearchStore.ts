import { create } from 'zustand';

// The "who mentioned" list Jessi already found during a live session, keyed by query, so the screen renders it instantly instead of searching twice.
type Preload = { query: string; days?: number | null; res: any; at: number };
type State = { preload: Preload | null; set: (query: string, res: any, days?: number | null) => void; take: (query: string) => Preload | null };

export const useMemorySearchStore = create<State>((set, get) => ({
  preload: null,
  set: (query, res, days) => set({ preload: { query: query.trim().toLowerCase(), res, days: days ?? null, at: Date.now() } }),
  take: (query) => {
    const p = get().preload;
    if (!p || p.query !== query.trim().toLowerCase() || Date.now() - p.at > 10 * 60 * 1000) return null;
    return p;
  },
}));
