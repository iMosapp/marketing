import { create } from 'zustand';

// Texting compliance + subscription access state shared by the API layer (services/api.ts) and the global sheets in app/_layout.tsx.
export type ConsentAsk = { code: string; message?: string; needs?: string[]; purpose?: string; contact_id?: string | null; phone?: string; name?: string; manual?: boolean };
export type BillingLock = { locked: boolean; owner?: boolean; message?: string; reason_text?: string; state?: string };
type Pending = ConsentAsk & { resolve: (ok: boolean) => void };

type ComplianceState = {
  ask: Pending | null;
  lock: BillingLock | null;
  consentRev: number;  // bumps whenever consent is recorded from the sheet, so open consent cards reload
  requestConsent: (a: ConsentAsk) => Promise<boolean>;
  settle: (ok: boolean) => void;
  setLock: (l: BillingLock | null) => void;
};

const DECLINE_QUIET_MS = 30000;
const declinedUntil = new Map<string, number>();
const inflight = new Map<string, Promise<boolean>>();
const askKey = (a: ConsentAsk) => a.phone || a.contact_id || 'unknown';
/** True while a "Not now" is still quieting the sheet for this number: callers then explain the refusal themselves. */
export const quieted = (a: ConsentAsk) => !a.manual && (declinedUntil.get(askKey(a)) || 0) > Date.now();

export const useCompliance = create<ComplianceState>((set, get) => ({
  ask: null,
  lock: null,
  consentRev: 0,
  // One sheet per number: parallel refused sends share it, and a "Not now" quiets repeats for 30 s (one tap never spawns five sheets).
  requestConsent: (a) => {
    const key = askKey(a);
    if (quieted(a)) return Promise.resolve(false);
    const running = inflight.get(key);
    if (running) return running;
    if (get().ask) return Promise.resolve(false);
    const p = new Promise<boolean>(resolve => set({ ask: { ...a, resolve } }));
    inflight.set(key, p);
    p.then(ok => { inflight.delete(key); if (!ok) declinedUntil.set(key, Date.now() + DECLINE_QUIET_MS); else declinedUntil.delete(key); });
    return p;
  },
  settle: (ok) => {
    const a = get().ask;
    set({ ask: null, ...(ok ? { consentRev: get().consentRev + 1 } : {}) });
    a?.resolve(ok);
  },
  setLock: (lock) => set({ lock }),
}));

export const CONSENT_CODES = ['consent_required', 'marketing_consent_required'];
