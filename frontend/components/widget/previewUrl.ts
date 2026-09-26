import { API_BASE_URL } from '../../services/api';

// ?c= carries unsaved look/copy so the preview page shows what the admin is typing before Save.
const b64url = (s: string) => {
  try {
    const bytes = encodeURIComponent(s).replace(/%([0-9A-F]{2})/g, (_, p) => String.fromCharCode(parseInt(p, 16)));
    return btoa(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  } catch { return ''; }
};

export const previewUrl = (key: string, config: { appearance: any; doors: any; copy: any }, bust: number) => {
  const c = b64url(JSON.stringify({ appearance: config.appearance, doors: config.doors, copy: config.copy }));
  return `${API_BASE_URL}/w/${key}/demo?v=${bust}${c ? `&c=${c}` : ''}`;
};

export type PreviewProps = { widgetKey: string; config: { appearance: any; doors: any; copy: any }; height?: number; colors: any };
