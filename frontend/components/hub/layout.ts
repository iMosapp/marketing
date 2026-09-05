import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../services/api';

export type HubApp = {
  id: string; title: string; subtitle: string; icon: string; color: string;
  badge?: number; statusDot?: 'green' | 'red' | 'grey'; onPress: () => void; folder: string;
};
export type HubFolderDef = { id: string; title: string; icon: string; color: string };
export type HubLayout = { v: 1; home: string[]; folders: Record<string, { title: string; items: string[] }>; updated_at?: string };

export const slug = (s: string) => s.toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
export const isFolderKey = (k: string) => k.startsWith('f:');
export const keyId = (k: string) => k.slice(2);

export function reconcile(layout: HubLayout | null | undefined, apps: HubApp[], folderDefs: HubFolderDef[], defaultLoose: string[]): HubLayout {
  const appIds = new Set(apps.map(a => a.id));
  const defs = Object.fromEntries(folderDefs.map(f => [f.id, f]));
  const next: HubLayout = layout && layout.v === 1
    ? { v: 1, home: [...layout.home], folders: Object.fromEntries(Object.entries(layout.folders).map(([k, f]) => [k, { title: f.title, items: [...f.items] }])), updated_at: layout.updated_at }
    : { v: 1, home: [], folders: {} };
  const fresh = !layout;

  // drop anything the user can no longer see
  for (const f of Object.values(next.folders)) f.items = f.items.filter(id => appIds.has(id));
  next.home = next.home.filter(k => (isFolderKey(k) ? !!next.folders[keyId(k)] : appIds.has(keyId(k))));

  const placed = new Set<string>();
  for (const f of Object.values(next.folders)) f.items.forEach(id => placed.add(id));
  next.home.forEach(k => { if (!isFolderKey(k)) placed.add(keyId(k)); });

  // seed loose favourites on a fresh layout
  if (fresh) for (const id of defaultLoose) if (appIds.has(id) && !placed.has(id)) { next.home.push(`a:${id}`); placed.add(id); }

  // new or unplaced apps land in their default folder (created on demand, in def order)
  for (const def of folderDefs) {
    for (const a of apps) {
      if (placed.has(a.id) || a.folder !== def.id) continue;
      if (!next.folders[def.id]) { next.folders[def.id] = { title: def.title, items: [] }; next.home.push(`f:${def.id}`); }
      next.folders[def.id].items.push(a.id);
      placed.add(a.id);
    }
  }
  for (const a of apps) if (!placed.has(a.id)) { next.home.push(`a:${a.id}`); placed.add(a.id); }

  // every folder is on home exactly once, empty folders vanish
  for (const fid of Object.keys(next.folders)) {
    if (next.folders[fid].items.length === 0) { delete next.folders[fid]; next.home = next.home.filter(k => k !== `f:${fid}`); }
    else if (!next.home.includes(`f:${fid}`)) next.home.push(`f:${fid}`);
  }
  next.home = Array.from(new Set(next.home));
  void defs;
  return next;
}

const key = (userId: string) => `hub_layout_v1:${userId}`;

export async function loadLayout(userId: string, remote?: HubLayout | null): Promise<HubLayout | null> {
  try {
    const raw = await AsyncStorage.getItem(key(userId));
    const local: HubLayout | null = raw ? JSON.parse(raw) : null;
    if (local && remote) return (remote.updated_at || '') > (local.updated_at || '') ? remote : local;
    return local || remote || null;
  } catch { return remote || null; }
}

export async function saveLayout(userId: string, layout: HubLayout) {
  const stamped = { ...layout, updated_at: new Date().toISOString() };
  try { await AsyncStorage.setItem(key(userId), JSON.stringify(stamped)); } catch { /* noop */ }
  api.patch(`/users/${userId}`, { hub_layout: stamped }).catch(() => { /* offline: local copy wins next time */ });
  return stamped;
}

export async function clearLayout(userId: string) {
  try { await AsyncStorage.removeItem(key(userId)); } catch { /* noop */ }
  api.patch(`/users/${userId}`, { hub_layout: null }).catch(() => { /* noop */ });
}
