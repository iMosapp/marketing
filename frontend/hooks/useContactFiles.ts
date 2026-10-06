import { useCallback, useEffect, useState } from 'react';
import api from '../services/api';

export type FilesMeta = { scan_types: Record<string, string>; sensitive_types: string[]; ttl_days: number };
const EMPTY_META: FilesMeta = { scan_types: {}, sensitive_types: [], ttl_days: 30 };

// Everything filed on one contact; loaded once the History tab opens so the Files chip can show its count.
export function useContactFiles(userId: string | undefined, contactId: string | undefined, enabled: boolean, onError?: (msg: string) => void) {
  const [files, setFiles] = useState<any[] | null>(null);
  const [meta, setMeta] = useState<FilesMeta>(EMPTY_META);

  const reload = useCallback(async () => {
    if (!userId || !contactId) return;
    try {
      const d = (await api.get(`/contact-files/${userId}/contact/${contactId}`)).data;
      setFiles(d.files || []);
      setMeta({ scan_types: d.scan_types || {}, sensitive_types: d.sensitive_types || [], ttl_days: d.ttl_days || 30 });
    } catch (e: any) { onError?.(e?.response?.data?.detail || 'Could not load files'); setFiles(prev => prev || []); }
  }, [userId, contactId]);

  useEffect(() => { if (enabled && files === null) reload(); }, [enabled, files, reload]);
  return { files, setFiles, meta, reload };
}

export type ContactFilesStore = ReturnType<typeof useContactFiles>;
