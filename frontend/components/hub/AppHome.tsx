import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, useWindowDimensions, Modal, Pressable, TextInput, StyleSheet, ScrollView } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Ionicons as Icon } from '@expo/vector-icons';
import { SortableGrid } from './SortableGrid';
import { AppTile, FolderTile, Jiggle, Landing } from './Tiles';
import { FolderModal } from './FolderModal';
import { MoveSheet } from './MoveSheet';
import { HubApp, HubFolderDef, HubLayout, RecentEntry, reconcile, loadLayout, saveLayout, clearLayout, isFolderKey, keyId, slug, mergeRecent, loadRecentLocal, fetchRecentRemote, saveRecent } from './layout';

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
  const [restoreFolder, setRestoreFolder] = useState(false);
  const [restorePage, setRestorePage] = useState(0);
  const returnFolder = useRef<{ id: string; page: number } | null>(null);
  const [moving, setMoving] = useState<{ app: HubApp; from: string | null } | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);
  const [landing, setLanding] = useState<string | null>(null);
  const [recent, setRecent] = useState<RecentEntry[]>([]);
  const recentRef = useRef<RecentEntry[]>([]);
  const saveTimer = useRef<any>(null);
  const recentTimer = useRef<any>(null);
  const synced = userId !== 'anon';

  useEffect(() => { loadLayout(userId, remoteLayout).then(l => setStored(l)); }, [userId]);

  const applyRecent = useCallback((list: RecentEntry[]) => { recentRef.current = list; setRecent(list); }, []);
  useEffect(() => { loadRecentLocal(userId).then(local => applyRecent(mergeRecent(local, recentRef.current))); }, [userId, applyRecent]);
  useFocusEffect(useCallback(() => {
    if (!synced) return;
    let alive = true;
    fetchRecentRemote(userId).then(remote => {
      if (!alive || !remote) return;
      const merged = mergeRecent(recentRef.current, remote);
      applyRecent(merged);
      saveRecent(userId, merged, false);
    });
    return () => { alive = false; };
  }, [userId, synced, applyRecent]));

  // Coming back from an app that was opened inside a folder lands you back inside that folder.
  useFocusEffect(useCallback(() => {
    if (!returnFolder.current) return;
    setRestoreFolder(true);
    setRestorePage(returnFolder.current.page);
    setOpenFolder(returnFolder.current.id);
    returnFolder.current = null;
  }, []));

  const launch = useCallback((app: HubApp) => {
    const next = mergeRecent([{ id: app.id, at: new Date().toISOString() }], recentRef.current);
    applyRecent(next);
    saveRecent(userId, next, false);
    if (recentTimer.current) clearTimeout(recentTimer.current);
    if (synced) recentTimer.current = setTimeout(() => saveRecent(userId, next, true), 600);
    app.onPress();
  }, [userId, synced, applyRecent]);

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
  const showFolder = (fid: string) => { setRestoreFolder(false); setOpenFolder(fid); };
  const open = (app: HubApp, page = 0) => { returnFolder.current = openFolder ? { id: openFolder, page } : null; setOpenFolder(null); setTimeout(() => launch(app), openFolder ? 120 : 0); };
  const flash = (id: string) => { setLanding(id); setTimeout(() => setLanding(null), 1700); };

  const dragOut = (app: HubApp, from: string) => {
    moveApp(app, from, { type: 'home' });
    setOpenFolder(null);
    flash(app.id);
  };

  const dropOnHome = (dragK: string, targetK: string) => {
    const app = byId[keyId(dragK)];
    if (!app) return;
    if (isFolderKey(targetK)) { moveApp(app, null, { type: 'folder', id: keyId(targetK) }); return; }
    const other = byId[keyId(targetK)];
    if (!other) return;
    const def = folderDefs.find(f => f.id === other.folder);
    const title = def?.title && !layout.folders[def.id] ? def.title : 'New Folder';
    const next: HubLayout = { ...layout, home: layout.home.filter(k => k !== dragK && k !== targetK), folders: { ...layout.folders } };
    let fid = slug(title) || `folder-${Date.now()}`;
    while (next.folders[fid]) fid = `${fid}-2`;
    next.folders[fid] = { title, items: [other.id, app.id] };
    next.home.push(`f:${fid}`);
    commit(next);
  };
  const canDropHome = (dragK: string, targetK: string) => !isFolderKey(dragK) && !!byId[keyId(dragK)] && (isFolderKey(targetK) || !!byId[keyId(targetK)]);
  const recentApps = recent.map(e => byId[e.id]).filter(Boolean).slice(0, 3) as HubApp[];

  const badgeTap = (fid: string) => {
    const waiting = folderApps(fid).filter(a => a.badge);
    if (waiting.length === 1) launch(waiting[0]); else showFolder(fid);
  };

  const folderDests = Object.entries(layout.folders).map(([id, f]) => ({ id, title: f.title, count: f.items.length }));

  return (
    <View style={{ paddingHorizontal: 16, paddingTop: 6 }} {...tid('app-home')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', minHeight: 30, marginBottom: 10 }}>
        <Text style={{ flex: 1, fontSize: 12, fontWeight: '700', letterSpacing: 1, color: colors.textTertiary || colors.textSecondary }}>{editing ? 'ARRANGE' : 'TOOLS'}</Text>
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
      {editing && (
        <Text style={{ fontSize: 11, color: colors.textTertiary || colors.textSecondary, marginTop: -4, marginBottom: 10 }} {...tid('arrange-hint')}>
          Drag to reorder. Hold a tool over a folder to file it, or over another tool to make a folder. Open a folder and pull a tool past the edge to bring it home.
        </Text>
      )}
      {recentApps.length > 0 && !editing && (
        <View style={{ marginBottom: 14 }} {...tid('recent-row')}>
          <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 1, color: colors.textTertiary || colors.textSecondary, marginBottom: 8 }}>RECENT</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            {recentApps.map(a => (
              <TouchableOpacity key={a.id} onPress={() => launch(a)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 6, paddingRight: 14, height: 40, borderRadius: 20, backgroundColor: colors.card, borderWidth: 1, borderColor: `${a.color}44` }} {...tid(`recent-${a.id}`)}>
                <View style={{ width: 28, height: 28, borderRadius: 9, backgroundColor: `${a.color}22`, alignItems: 'center', justifyContent: 'center' }}><Icon name={a.icon as any} size={15} color={a.color} /></View>
                <View>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }} numberOfLines={1}>{a.title}</Text>
                  {!!a.badge && <Text style={{ fontSize: 10, fontWeight: '700', color: '#FF3B30' }}>{a.badge} waiting</Text>}
                </View>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      )}
      <View style={{ alignItems: 'center' }}>
        <SortableGrid
          testID="home-grid"
          items={homeItems} columns={columns} cellW={cellW} cellH={cellH} gap={gap} editing={editing}
          canDropOn={canDropHome}
          onDropOn={dropOnHome}
          renderItem={(key, dragging, hovered) => {
            const jig = editing && !dragging && !hovered;
            if (isFolderKey(key)) {
              const fid = keyId(key);
              return <Jiggle on={jig} seed={key.length}><FolderTile title={layout.folders[fid]?.title || fid} apps={folderApps(fid)} size={cellW} colors={colors} editing={editing} badge={folderBadge(fid)} hovered={hovered} onBadgePress={editing || dragging ? undefined : () => badgeTap(fid)} /></Jiggle>;
            }
            const a = byId[keyId(key)];
            return a ? <Jiggle on={jig} seed={key.length}><Landing on={landing === a.id}><AppTile app={a} size={cellW} colors={colors} editing={editing} hovered={hovered} /></Landing></Jiggle> : null;
          }}
          onPress={key => {
            if (isFolderKey(key)) {
              if (editing) setRenaming({ id: keyId(key), title: layout.folders[keyId(key)]?.title || '' });
              else showFolder(keyId(key));
              return;
            }
            const a = byId[keyId(key)];
            if (!a) return;
            if (editing) setMoving({ app: a, from: null }); else launch(a);
          }}
          onLongPress={() => setEditing(true)}
          onReorder={reorderHome}
          onDragging={onDragging}
        />
      </View>

      {openFolder && layout.folders[openFolder] && (
        <FolderModal
          visible title={layout.folders[openFolder].title} apps={folderApps(openFolder)} colors={colors} editing={editing}
          onClose={() => setOpenFolder(null)} onOpenApp={open} restore={restoreFolder} initialPage={restoreFolder ? restorePage : 0}
          onStartEditing={() => setEditing(true)} onStopEditing={() => setEditing(false)}
          onReorder={ids => reorderFolder(openFolder, ids)} onRename={t => renameFolder(openFolder, t)}
          onMoveRequest={a => setMoving({ app: a, from: openFolder })}
          onDragOut={a => dragOut(a, openFolder)}
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
              <Text style={{ fontSize: 11, color: colors.textSecondary }}>Removing a folder puts its tools back on the home screen.</Text>
            </View>
          </View>
        </Modal>
      )}
    </View>
  );
};
