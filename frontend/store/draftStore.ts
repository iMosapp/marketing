import { create } from 'zustand';

// Drafts Jessi parks in a thread's composer during a live session, keyed by contact id, so the thread picks them up instantly if it is already open.
type DraftState = { drafts: Record<string, { text: string; at: number }>; set: (contactId: string, text: string) => void; clear: (contactId: string) => void };

export const useDraftStore = create<DraftState>((set) => ({
  drafts: {},
  set: (contactId, text) => set(s => ({ drafts: { ...s.drafts, [contactId]: { text, at: Date.now() } } })),
  clear: (contactId) => set(s => { const next = { ...s.drafts }; delete next[contactId]; return { drafts: next }; }),
}));
