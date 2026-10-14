import { create } from 'zustand';
import api from '../services/api';

// Short-lived, user-bound token the backend requires on media fetched by URL (<audio>/<Image> cannot send a Bearer header):
// call recordings (/api/calls/recording/{sid}) and proxied Twilio media. resolvePhotoUrl appends it as ?t=.
type S = { token: string | null; expiresAt: number; userId: string | null; ensure: (userId: string) => Promise<void>; clear: () => void };

let inflight: Promise<void> | null = null;

export const useMediaTokenStore = create<S>((set, get) => ({
  token: null,
  expiresAt: 0,
  userId: null,
  ensure: async (userId) => {
    const s = get();
    if (s.token && s.userId === userId && s.expiresAt - Date.now() > 15 * 60 * 1000) return;
    if (inflight) return inflight;
    inflight = api.get('/calls/recording-token')
      .then(r => set({ token: r.data.token, expiresAt: Date.now() + (r.data.expires_in || 7200) * 1000, userId }))
      .catch(() => {})
      .finally(() => { inflight = null; });
    return inflight;
  },
  clear: () => set({ token: null, expiresAt: 0, userId: null }),
}));

export const MEDIA_TOKEN_PATHS = /\/api\/(webhooks\/twilio\/media-proxy|calls\/recording\/)/;

export const withMediaToken = (url: string): string => {
  if (!MEDIA_TOKEN_PATHS.test(url) || /[?&]t=/.test(url)) return url;
  const t = useMediaTokenStore.getState().token;
  return t ? `${url}${url.includes('?') ? '&' : '?'}t=${encodeURIComponent(t)}` : url;
};
