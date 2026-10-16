import { useEffect, useState } from 'react';
import api from '../services/api';
import { Picked, takePhoto, choosePhotos, chooseFiles } from './useContactFileUpload';

export type ScanSource = 'camera' | 'library' | 'document';
export type ScanMatch = { id: string; name: string; phone: string; email: string; company: string; why: string[]; current: Record<string, string> };
export type ScanResult = { scan: any; matches: ScanMatch[] };

const PIECE = 500_000;
let cached: { enabled: boolean; paused: boolean } | null = null;

// Is Scan with Jessi on for this rep (Photo Intelligence rollout + Pause All)? Asked once per app session.
export function useScanStatus(userId?: string) {
  const [s, setS] = useState(cached);
  useEffect(() => {
    if (!userId || cached) return;
    api.get(`/scan/${userId}/status`).then(r => { cached = r.data; setS(r.data); }).catch(() => {});
  }, [userId]);
  return s;
}

// Pick (camera / photo / PDF) -> base64 pieces -> /scan. Jessi reads it on the last piece; returns the review + possible matches.
export function useScanUpload(userId: string | undefined, onDone: (r: ScanResult) => void, onError: (m: string) => void) {
  const [busy, setBusy] = useState('');
  const send = async (p: Picked, capture: ScanSource) => {
    const total = Math.max(1, Math.ceil(p.base64.length / PIECE));
    const uploadId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    let last: any = null;
    for (let i = 0; i < total; i++) {
      setBusy(i === total - 1 ? 'Jessi is reading it…' : `Uploading ${Math.round(((i + 1) / total) * 100)}%`);
      const r = await api.post(`/scan/${userId}/chunk`, { upload_id: uploadId, index: i, total, data: p.base64.slice(i * PIECE, (i + 1) * PIECE), name: p.name, content_type: p.contentType, capture }, { timeout: 180000 });
      last = r.data;
    }
    if (last?.scan) onDone({ scan: last.scan, matches: last.matches || [] });
  };
  const run = async (capture: ScanSource) => {
    if (!userId) return;
    try {
      const items = capture === 'camera' ? await takePhoto() : capture === 'library' ? await choosePhotos(false) : await chooseFiles(false, onError);
      if (items[0]) await send(items[0], capture);
    } catch (e: any) {
      onError(e?.response?.data?.detail || (e instanceof Error && e.message.startsWith('Camera access') ? e.message : 'Could not scan that. Please try again.'));
    } finally { setBusy(''); }
  };
  return { busy, run };
}
