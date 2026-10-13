import { useCallback, useEffect, useState } from 'react';
import api from '../../services/api';

export type LiveConfig = {
  available: boolean; is_super_admin: boolean; configured: boolean; reason?: string | null;
  voice: string; greeting: string; idle_close_s: number; usage: { used_s: number; cap_s: number; left_s: number; reset_at?: string };
  controls?: { premium_left_s: number; backup_left_s: number; next_engine: string | null; killed?: boolean } | null;
};

export const useLiveConfig = () => {
  const [config, setConfig] = useState<LiveConfig | null>(null);
  const reload = useCallback(async () => {
    try { const r = await api.get('/live-voice/config'); setConfig(r.data); } catch { setConfig(null); }
  }, []);
  useEffect(() => { reload(); }, [reload]);
  return { config, reload };
};
