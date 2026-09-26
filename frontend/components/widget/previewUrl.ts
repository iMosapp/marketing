import { API_BASE_URL } from '../../services/api';

// ?c= carries unsaved look/copy so the preview page shows what the admin is typing before Save.
const b64url = (s: string) => {
  try {
    const bytes = encodeURIComponent(s).replace(/%([0-9A-F]{2})/g, (_, p) => String.fromCharCode(parseInt(p, 16)));
    return btoa(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  } catch { return ''; }
};

export type PreviewConfig = { appearance: any; doors: any; copy: any; kb?: any; path?: string; door?: string };

// `path` fakes the visitor's page address (page greetings), `door` opens straight into one door.
export const previewUrl = (key: string, config: PreviewConfig, bust: number) => {
  const c = b64url(JSON.stringify({ appearance: config.appearance, doors: config.doors, copy: config.copy, kb: config.kb ? { welcome: config.kb.welcome } : undefined }));
  const extra = `${config.path ? `&path=${encodeURIComponent(config.path)}` : ''}${config.door ? `&door=${config.door}` : ''}`;
  return `${API_BASE_URL}/w/${key}/demo?v=${bust}${c ? `&c=${c}` : ''}${extra}`;
};

export type PreviewProps = { widgetKey: string; config: PreviewConfig; height?: number; colors: any };
