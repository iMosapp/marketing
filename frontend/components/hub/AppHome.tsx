import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, useWindowDimensions, Modal, Pressable, TextInput, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SortableGrid } from './SortableGrid';
import { AppTile, FolderTile, Jiggle } from './Tiles';
import { FolderModal } from './FolderModal';
import { MoveSheet } from './MoveSheet';
import { HubApp, HubFolderDef, HubLayout, reconcile, loadLayout, saveLayout, clearLayout, isFolderKey, keyId, slug } from './layout';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Props = { apps: HubApp[]; folderDefs: HubFolderDef[]; defaultLoose: string[]; userId: string; remoteLayout?: HubLayout | null; colors: any; onDragging?: (active: boolean) => void };

export const AppHome = ({ apps, folderDefs, defaultLoose, userId, remoteLayout, colors, onDragging }: Props) => {
  const { width } = useWindowDimensions();
  const columns = 4;
  const gap = 14;
  const gridW = Math.min(width, 480) - 32;
  const cellW = Math.floor((gridW - gap * (columns - 1)) / columns);
  const cellH = cellW + 34;

  const [stored, setStored] = useState<HubLayout | null | undefined>(undefined);
  const [editing, setEditing] = useState(false);
  const [openFolder, setOpenFolder] = useState<string | null>(null);
  const [moving, setMoving] = useState<{ app: HubApp; from: string | null } | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);
  const saveTimer = useRef<any>(null);

  useEffect(() => { loadLayout(userId, remoteLayout).then(l => setStored(l)); }, [userId]);

  const byId = useMemo(() => Object.fromEntries(apps.map(a => [a.id, a])), [apps]);
  const layout = useMemo(() => (stored === undefined ? null : reconcile(stored, apps, folderDefs, defaultLoose)), [stored, apps, folderDefs, defaultLoose]);

  const commit = useCallback((next: HubLayout) => {
    setStored(next);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => saveLayout(userId, next), 400);
  }, [userId]);

  if (!layout) return <View style={{ height: 200 }} />;

  const folderApps = (fid: string) => (layout.folders[fid]?.items || []).map(id => byId[id]).filter(Boolean) as HubApp[];
  const folderBadge = (fid: string) => folderApps(fid).reduce((n, a) => n + (a.badge || 0), 0);
  const homeItems = layout.home.map(k => ({ key: k }));

  const reorderHome = (keys: string[]) => commit({ ...layout, home: keys });
  const reorderFolder = (fid: string, ids: string[]) => commit({ ...layout, folders: { ...layout.folders, [fid]: { ...layout.folders[fid], items: ids } } });
  const renameFolder = (fid: string, title: string) => commit({ ...layout, folders: { ...layout.folders, [fid]: { ...layout.folders[fid], title } } });

  const moveApp = (app: HubApp, from: string | null, dest: { type: 'home' } | { type: 'folder'; id: string } | { type: 'new'; title: string }) => {
    const next: HubLayout = { ...layout, home: [...layout.home], folders: Object.fromEntries(Object.entries(layout.folders).map(([k, f]) => [k, { ...f, items: [...f.items] }])) };
    if (from) next.folders[from].items = next.folders[from].items.filter(id => id !== app.id);
    else next.home = next.home.filter(k => k !== `a:${app.id}`);
    if (dest.type === 'home') next.home.push(`a:${app.id}`);
    else if (dest.type === 'folder') next.folders[dest.id].items.push(app.id);
    else {
      let fid = slug(dest.title) || `folder-${Date.now()}`;
      while (next.folders[fid]) fid = `${fid}-2`;
      next.folders[fid] = { title: dest.title, items: [app.id] };
      next.home.push(`f:${fid}`);
    }
    for (const fid of Object.keys(next.folders)) if (next.folders[fid].items.length === 0) { delete next.folders[fid]; next.home = next.home.filter(k => k !== `f:${fid}`); }
    commit(next);
    setMoving(null);
    if (from && !next.folders[from]) setOpenFolder(null);
  };

  const dissolveFolder = (fid: string) => {
    const next: HubLayout = { ...layout, home: layout.home.filter(k => k !== `f:${fid}`), folders: { ...layout.folders } };
    next.folders[fid].items.forEach(id => next.home.push(`a:${id}`));
    delete next.folders[fid];
    commit(next);
    setRenaming(null);
  };

  const reset = async () => { await clearLayout(userId); setStored(null); setEditing(false); };
  const open = (app: HubApp) => { setOpenFolder(null); setTimeout(() => app.onPress(), openFolder ? 120 : 0); };

  const folderDests = Object.entries(layout.folders).map(([id, f]) => ({ id, title: f.title, count: f.items.length }));

  return (
    <View style={{ paddingHorizontal: 16, paddingTop: 6 }} {...tid('app-home')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', minHeight: 30, marginBottom: 10 }}>
        <Text style={{ flex: 1, fontSize: 12, fontWeight: '700', letterSpacing: 1, color: colors.textTertiary || colors.textSecondary }}>{editing ? 'ARRANGE' : 'APPS'}</Text>
        {editing ? (
          <>
            <TouchableOpacity onPress={reset} style={{ paddingHorizontal: 12, height: 30, borderRadius: 15, justifyContent: 'center' }} {...tid('apps-reset')}>
              <Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary }}>Reset</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setEditing(false)} style={{ paddingHorizontal: 14, height: 30, borderRadius: 15, backgroundColor: GOLD, justifyContent: 'center' }} {...tid('apps-done')}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: '#000' }}>Done</Text>
            </TouchableOpacity>
          </>
        ) : (
          <Text style={{ fontSize: 11, color: colors.textTertiary || colors.textSecondary }}>Hold to rearrange</Text>
        )}
      </View>
      <View style={{ alignItems: 'center' }}>
        <SortableGrid
          testID="home-grid"
          items={homeItems} columns={columns} cellW={cellW} cellH={cellH} gap={gap} editing={editing}
          renderItem={(key, dragging) => {
            const jig = editing && !dragging;
            if (isFolderKey(key)) {
              const fid = keyId(key);
              return <Jiggle on={jig} seed={key.length}><FolderTile title={layout.folders[fid]?.title || fid} apps={folderApps(fid)} size={cellW} colors={colors} editing={editing} badge={folderBadge(fid)} /></Jiggle>;
            }
            const a = byId[keyId(key)];
            return a ? <Jiggle on={jig} seed={key.length}><AppTile app={a} size={cellW} colors={colors} editing={editing} /></Jiggle> : null;
          }}
          onPress={key => {
            if (isFolderKey(key)) {
              if (editing) setRenaming({ id: keyId(key), title: layout.folders[keyId(key)]?.title || '' });
              else setOpenFolder(keyId(key));
              return;
            }
            const a = byId[keyId(key)];
            if (!a) return;
            if (editing) setMoving({ app: a, from: null }); else a.onPress();
          }}
          onLongPress={() => setEditing(true)}
          onReorder={reorderHome}
          onDragging={onDragging}
        />
      </View>

      {openFolder && layout.folders[openFolder] && (
        <FolderModal
          visible title={layout.folders[openFolder].title} apps={folderApps(openFolder)} colors={colors} editing={editing}
          onClose={() => setOpenFolder(null)} onOpenApp={open}
          onStartEditing={() => setEditing(true)} onStopEditing={() => setEditing(false)}
          onReorder={ids => reorderFolder(openFolder, ids)} onRename={t => renameFolder(openFolder, t)}
          onMoveRequest={a => setMoving({ app: a, from: openFolder })}
        />
      )}

      {moving && (
        <MoveSheet app={moving.app} currentFolder={moving.from} folders={folderDests} colors={colors} onClose={() => setMoving(null)} onMove={d => moveApp(moving.app, moving.from, d)} />
      )}

      {renaming && (
        <Modal visible transparent animationType="fade" onRequestClose={() => setRenaming(null)}>
          <Pressable style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.6)' }]} onPress={() => setRenaming(null)} />
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 }} pointerEvents="box-none">
            <View style={{ width: '100%', maxWidth: 380, backgroundColor: colors.surface || colors.card, borderRadius: 20, padding: 18, gap: 12 }} {...tid('folder-rename-sheet')}>
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Folder name</Text>
              <TextInput value={renaming.title} onChangeText={t => setRenaming({ ...renaming, title: t })} autoFocus
                style={{ height: 44, borderRadius: 10, paddingHorizontal: 12, backgroundColor: colors.bg, color: colors.text, fontSize: 16, borderWidth: 1, borderColor: `${GOLD}66` }} {...tid('folder-rename-home-input')} />
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <TouchableOpacity onPress={() => dissolveFolder(renaming.id)} style={{ flex: 1, height: 42, borderRadius: 10, borderWidth: 1, borderColor: '#FF3B3066', alignItems: 'center', justifyContent: 'center' }} {...tid('folder-dissolve')}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: '#FF3B30' }}>Remove folder</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => { if (renaming.title.trim()) renameFolder(renaming.id, renaming.title.trim()); setRenaming(null); }} style={{ flex: 1, height: 42, borderRadius: 10, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('folder-rename-save')}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: '#000' }}>Save</Text>
                </TouchableOpacity>
              </View>
              <Text style={{ fontSize: 11, color: colors.textSecondary }}>Removing a folder puts its apps back on the home screen.</Text>
            </View>
          </View>
        </Modal>
      )}
    </View>
  );
};
