import React, { useState } from 'react';
import { View, Text, Modal, Pressable, TouchableOpacity, TextInput, ScrollView, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { HubApp } from './layout';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Dest = { id: string; title: string; count: number };
type Props = {
  app: HubApp | null;
  currentFolder: string | null;
  folders: Dest[];
  colors: any;
  onClose: () => void;
  onMove: (dest: { type: 'home' } | { type: 'folder'; id: string } | { type: 'new'; title: string }) => void;
};

const Row = ({ icon, color, title, sub, onPress, colors, id, active }: { icon: any; color: string; title: string; sub?: string; onPress: () => void; colors: any; id: string; active?: boolean }) => (
  <TouchableOpacity onPress={onPress} disabled={active} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, opacity: active ? 0.45 : 1 }} {...tid(id)}>
    <View style={{ width: 34, height: 34, borderRadius: 10, backgroundColor: `${color}22`, alignItems: 'center', justifyContent: 'center' }}><Ionicons name={icon} size={17} color={color} /></View>
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{title}</Text>
      {!!sub && <Text style={{ fontSize: 12, color: colors.textSecondary }}>{sub}</Text>}
    </View>
    {active ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>Here now</Text> : <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />}
  </TouchableOpacity>
);

export const MoveSheet = ({ app, currentFolder, folders, colors, onClose, onMove }: Props) => {
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  if (!app) return null;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.6)' }]} onPress={onClose} {...tid('move-backdrop')} />
      <View style={{ flex: 1, justifyContent: 'flex-end' }} pointerEvents="box-none">
        <View style={{ backgroundColor: colors.surface || colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34, maxHeight: '75%' }} {...tid('move-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: `${app.color}22`, alignItems: 'center', justifyContent: 'center' }}><Ionicons name={app.icon as any} size={20} color={app.color} /></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{`Move "${app.title}"`}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>Pick where it should live</Text>
            </View>
            <TouchableOpacity onPress={onClose} {...tid('move-close')}><Ionicons name="close-circle" size={24} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <ScrollView showsVerticalScrollIndicator={false}>
            <Row id="move-home" icon="home" color={GOLD} title="Home screen" sub="Sits out on the grid" colors={colors} active={currentFolder === null} onPress={() => onMove({ type: 'home' })} />
            {folders.map(f => (
              <Row key={f.id} id={`move-folder-${f.id}`} icon="folder" color="#007AFF" title={f.title} sub={`${f.count} app${f.count === 1 ? '' : 's'}`} colors={colors} active={currentFolder === f.id} onPress={() => onMove({ type: 'folder', id: f.id })} />
            ))}
            {creating ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8 }}>
                <TextInput value={newName} onChangeText={setNewName} placeholder="Folder name" placeholderTextColor={colors.textSecondary} autoFocus
                  style={{ flex: 1, height: 42, borderRadius: 10, paddingHorizontal: 12, backgroundColor: colors.bg, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: `${GOLD}66` }} {...tid('move-new-folder-input')} />
                <TouchableOpacity onPress={() => newName.trim() && onMove({ type: 'new', title: newName.trim() })} style={{ height: 42, paddingHorizontal: 16, borderRadius: 10, backgroundColor: GOLD, justifyContent: 'center' }} {...tid('move-new-folder-create')}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: '#000' }}>Create</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <Row id="move-new-folder" icon="add-circle" color="#34C759" title="New folder" sub="Create one and put it there" colors={colors} onPress={() => setCreating(true)} />
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};
