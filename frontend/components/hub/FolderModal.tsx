import React, { useMemo, useState } from 'react';
import { View, Text, Modal, Pressable, TouchableOpacity, TextInput, ScrollView, useWindowDimensions, Platform, StyleSheet } from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeIn, FadeOut, ZoomIn } from 'react-native-reanimated';
import { SortableGrid } from './SortableGrid';
import { AppTile, Jiggle } from './Tiles';
import type { HubApp } from './layout';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Props = {
  visible: boolean;
  title: string;
  apps: HubApp[];
  colors: any;
  editing: boolean;
  onClose: () => void;
  onOpenApp: (app: HubApp) => void;
  onStartEditing: () => void;
  onStopEditing: () => void;
  onReorder: (ids: string[]) => void;
  onRename: (title: string) => void;
  onMoveRequest: (app: HubApp) => void;
};

export const FolderModal = ({ visible, title, apps, colors, editing, onClose, onOpenApp, onStartEditing, onStopEditing, onReorder, onRename, onMoveRequest }: Props) => {
  const { width, height } = useWindowDimensions();
  const cardW = Math.min(width - 24, 440);
  const columns = 4;
  const gap = 12;
  const cellW = Math.floor((cardW - 32 - gap * (columns - 1)) / columns);
  const cellH = cellW + 34;
  const [name, setName] = useState(title);
  const byId = useMemo(() => Object.fromEntries(apps.map(a => [a.id, a])), [apps]);
  const items = useMemo(() => apps.map(a => ({ key: a.id })), [apps]);
  const maxGridH = height * 0.62;

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
      <Animated.View entering={FadeIn.duration(160)} exiting={FadeOut.duration(140)} style={StyleSheet.absoluteFill}>
        <Pressable style={StyleSheet.absoluteFill} onPress={editing ? onStopEditing : onClose} {...tid('folder-backdrop')}>
          {Platform.OS === 'web'
            ? <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.72)' }]} />
            : <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFill} />}
          <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.35)' }]} />
        </Pressable>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 12 }} pointerEvents="box-none">
          <Animated.View entering={ZoomIn.springify().damping(18).stiffness(220)} style={{ width: cardW, borderRadius: 28, backgroundColor: colors.surface || colors.card, borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)', padding: 16, paddingTop: 14 }} {...tid('folder-modal')}>
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
            <ScrollView style={{ maxHeight: maxGridH }} contentContainerStyle={{ alignItems: 'center' }} showsVerticalScrollIndicator={false} scrollEnabled={!editing}>
              <SortableGrid
                testID="folder-grid"
                items={items} columns={columns} cellW={cellW} cellH={cellH} gap={gap} editing={editing}
                renderItem={(key, dragging) => {
                  const a = byId[key];
                  if (!a) return null;
                  return <Jiggle on={editing && !dragging} seed={key.length}><AppTile app={a} size={cellW} colors={colors} editing={editing} /></Jiggle>;
                }}
                onPress={key => { const a = byId[key]; if (!a) return; if (editing) onMoveRequest(a); else onOpenApp(a); }}
                onLongPress={onStartEditing}
                onReorder={onReorder}
              />
            </ScrollView>
            <Text style={{ fontSize: 11, color: colors.textTertiary || colors.textSecondary, textAlign: 'center', marginTop: 12 }}>
              {editing ? 'Drag to reorder. Tap an app to move it somewhere else.' : 'Hold any app to rearrange or rename this folder.'}
            </Text>
          </Animated.View>
        </View>
      </Animated.View>
    </Modal>
  );
};
