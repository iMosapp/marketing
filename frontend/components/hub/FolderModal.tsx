import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, Modal, Pressable, TouchableOpacity, TextInput, ScrollView, useWindowDimensions, Platform, StyleSheet } from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeIn, FadeOut, ZoomIn, Easing } from 'react-native-reanimated';
import { SortableGrid } from './SortableGrid';
import { AppTile, Jiggle, Landing } from './Tiles';
import type { HubApp } from './layout';

const GOLD = '#C9A962';
const PAGE_SIZE = 8;
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Props = {
  visible: boolean;
  title: string;
  apps: HubApp[];
  colors: any;
  editing: boolean;
  onClose: () => void;
  onOpenApp: (app: HubApp, page: number) => void;
  onStartEditing: () => void;
  onStopEditing: () => void;
  onReorder: (ids: string[]) => void;
  onRename: (title: string) => void;
  onMoveRequest: (app: HubApp) => void;
  onDragOut: (app: HubApp) => void;
  /** true when re-opening the folder the user just came back from: no zoom, just appear */
  restore?: boolean;
  initialPage?: number;
};

const chunk = <T,>(list: T[], size: number): T[][] => {
  const out: T[][] = [];
  for (let i = 0; i < list.length; i += size) out.push(list.slice(i, i + size));
  return out.length ? out : [[]];
};

export const FolderModal = ({ visible, title, apps, colors, editing, onClose, onOpenApp, onStartEditing, onStopEditing, onReorder, onRename, onMoveRequest, onDragOut, restore, initialPage = 0 }: Props) => {
  const { width } = useWindowDimensions();
  const cardW = Math.min(width - 24, 440);
  const innerW = cardW - 32;
  const columns = 4;
  const gap = 12;
  const cellW = Math.floor((innerW - gap * (columns - 1)) / columns);
  const cellH = cellW + 34;
  const [name, setName] = useState(title);
  const [landing, setLanding] = useState<string | null>(null);
  const byId = useMemo(() => Object.fromEntries(apps.map(a => [a.id, a])), [apps]);
  const pages = useMemo(() => chunk(apps, PAGE_SIZE), [apps]);
  const paged = pages.length > 1;
  const rows = Math.max(1, Math.ceil(Math.min(apps.length, PAGE_SIZE) / columns));
  const gridH = rows * (cellH + gap) - gap;
  const [page, setPage] = useState(Math.min(initialPage, pages.length - 1));
  const pagerRef = useRef<ScrollView>(null);

  const goTo = (i: number, animated = true) => {
    const p = Math.max(0, Math.min(i, pages.length - 1));
    setPage(p);
    pagerRef.current?.scrollTo({ x: p * innerW, y: 0, animated });
  };
  useEffect(() => { if (initialPage > 0) setTimeout(() => goTo(initialPage, false), 0); }, []);
  useEffect(() => { if (page > pages.length - 1) goTo(pages.length - 1); }, [pages.length]);

  const flash = (id: string) => { setLanding(id); setTimeout(() => setLanding(null), 1500); };
  const reorderPage = (pi: number, ids: string[]) => onReorder(pages.flatMap((p, i) => (i === pi ? ids : p.map(a => a.id))));
  const hop = (pi: number, key: string, dir: 'left' | 'right') => {
    const to = dir === 'right' ? pi + 1 : pi - 1;
    if (to < 0 || to >= pages.length) return;
    const ids = apps.map(a => a.id).filter(id => id !== key);
    ids.splice(dir === 'right' ? to * PAGE_SIZE : pi * PAGE_SIZE - 1, 0, key);
    onReorder(ids);
    goTo(to);
    flash(key);
  };

  const hint = editing
    ? paged
      ? 'Drag to reorder. Hold an app at the side to move it to the next page, or pull it above or below to drop it on the home screen. Tap one to move it.'
      : 'Drag to reorder, or pull an app past the edge to drop it on the home screen. Tap one to move it.'
    : paged ? 'Swipe for more. Hold any app to rearrange or rename this folder.' : 'Hold any app to rearrange or rename this folder.';

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
      <Animated.View entering={FadeIn.duration(restore ? 80 : 160)} exiting={FadeOut.duration(140)} style={StyleSheet.absoluteFill}>
        <Pressable style={StyleSheet.absoluteFill} onPress={editing ? onStopEditing : onClose} {...tid('folder-backdrop')}>
          {Platform.OS === 'web'
            ? <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.72)' }]} />
            : <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFill} />}
          <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.35)' }]} />
        </Pressable>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 12 }} pointerEvents="box-none">
          <Animated.View entering={restore ? FadeIn.duration(80) : ZoomIn.duration(180).easing(Easing.out(Easing.cubic))} style={{ width: cardW, borderRadius: 28, backgroundColor: colors.surface || colors.card, borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)', padding: 16, paddingTop: 14 }} {...tid('folder-modal')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              {editing ? (
                <TextInput value={name} onChangeText={setName} onBlur={() => name.trim() && onRename(name.trim())} onSubmitEditing={() => name.trim() && onRename(name.trim())}
                  style={{ flex: 1, fontSize: 18, fontWeight: '700', color: colors.text, backgroundColor: colors.bg, borderRadius: 10, paddingHorizontal: 10, height: 38, borderWidth: 1, borderColor: `${GOLD}66` }} {...tid('folder-rename-input')} />
              ) : (
                <Text style={{ flex: 1, fontSize: 18, fontWeight: '700', color: colors.text }} numberOfLines={1} {...tid('folder-title')}>{title}</Text>
              )}
              <TouchableOpacity onPress={editing ? onStopEditing : onStartEditing} style={{ paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: editing ? GOLD : colors.bg, justifyContent: 'center' }} {...tid('folder-edit-toggle')}>
                <Text style={{ fontSize: 13, fontWeight: '700', color: editing ? '#000' : colors.textSecondary }}>{editing ? 'Done' : 'Edit'}</Text>
              </TouchableOpacity>
              {!editing && (
                <TouchableOpacity onPress={onClose} style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }} {...tid('folder-close')}>
                  <Ionicons name="close" size={18} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
            </View>
            <ScrollView
              ref={pagerRef}
              horizontal pagingEnabled showsHorizontalScrollIndicator={false}
              scrollEnabled={paged && !editing}
              scrollEventThrottle={16}
              onScroll={e => { const p = Math.round(e.nativeEvent.contentOffset.x / innerW); if (p !== page && p >= 0 && p < pages.length) setPage(p); }}
              style={{ width: innerW, height: gridH }}
              {...tid('folder-pager')}
            >
              {pages.map((pageApps, pi) => (
                <View key={pi} style={{ width: innerW, alignItems: 'center' }} {...tid(`folder-page-${pi}`)}>
                  <SortableGrid
                    testID={pi === 0 ? 'folder-grid' : `folder-grid-${pi}`}
                    items={pageApps.map(a => ({ key: a.id }))} columns={columns} cellW={cellW} cellH={cellH} gap={gap} editing={editing}
                    renderItem={(key, dragging) => {
                      const a = byId[key];
                      if (!a) return null;
                      return <Jiggle on={editing && !dragging} seed={key.length}><Landing on={landing === key}><AppTile app={a} size={cellW} colors={colors} editing={editing} /></Landing></Jiggle>;
                    }}
                    onPress={key => { const a = byId[key]; if (!a) return; if (editing) onMoveRequest(a); else onOpenApp(a, pi); }}
                    onLongPress={onStartEditing}
                    onReorder={ids => reorderPage(pi, ids)}
                    onDragOutside={key => { const a = byId[key]; if (a) onDragOut(a); }}
                    outsideMargin={48}
                    outsideAxis={paged ? 'vertical' : 'both'}
                    onEdgeHold={paged ? (key, dir) => hop(pi, key, dir) : undefined}
                  />
                </View>
              ))}
            </ScrollView>
            {paged && (
              <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 7, marginTop: 12 }} {...tid('folder-dots')}>
                {pages.map((_, i) => (
                  <TouchableOpacity key={i} onPress={() => goTo(i)} hitSlop={8} {...tid(`folder-dot-${i}`)}>
                    <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: i === page ? GOLD : 'rgba(255,255,255,0.28)' }} />
                  </TouchableOpacity>
                ))}
              </View>
            )}
            <Text style={{ fontSize: 11, color: colors.textTertiary || colors.textSecondary, textAlign: 'center', marginTop: paged ? 8 : 12 }} {...tid('folder-hint')}>{hint}</Text>
          </Animated.View>
        </View>
      </Animated.View>
    </Modal>
  );
};
