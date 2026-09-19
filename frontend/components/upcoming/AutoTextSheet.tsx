import React, { useState } from 'react';
import { Modal, View, Text, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { tid } from '../scripts/shared';
import { GOLD, UpcomingItem, dayLabel } from './types';

type Props = {
  item: UpcomingItem | null;
  today: string;
  onClose: () => void;
  onSendNow: (item: UpcomingItem) => Promise<void>;
  onCancel: (item: UpcomingItem) => Promise<void>;
  onOpenContact: (item: UpcomingItem) => void;
};

export const AutoTextSheet = ({ item, today, onClose, onSendNow, onCancel, onOpenContact }: Props) => {
  const { colors } = useThemeStore();
  const [busy, setBusy] = useState<'send' | 'cancel' | null>(null);
  if (!item) return null;
  const jessi = item.owner === 'jessi';
  const run = async (which: 'send' | 'cancel') => {
    setBusy(which);
    try { await (which === 'send' ? onSendNow(item) : onCancel(item)); } finally { setBusy(null); }
  };
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }}>
        <TouchableOpacity activeOpacity={1} style={{ backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 34, borderWidth: 1, borderColor: colors.border }} {...tid('auto-text-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <View style={{ paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, backgroundColor: jessi ? 'rgba(201,169,98,0.14)' : 'rgba(90,200,250,0.14)' }}>
              <Text style={{ fontSize: 11, fontWeight: '700', color: jessi ? GOLD : '#5AC8FA' }}>{jessi ? 'JESSI SENDS' : 'YOU SEND'}</Text>
            </View>
            <Text style={{ fontSize: 13, color: colors.textSecondary }}>{dayLabel(item.date, today)}{item.time ? ` · ${item.time}` : ''}</Text>
          </View>
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{item.title}</Text>
          <TouchableOpacity onPress={() => onOpenContact(item)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 }} {...tid('auto-text-open-contact')}>
            <Text style={{ fontSize: 14, color: GOLD, fontWeight: '600' }}>{item.contact_name || item.contact_phone || 'Contact'}</Text>
            <Ionicons name="chevron-forward" size={14} color={GOLD} />
          </TouchableOpacity>

          <ScrollView style={{ maxHeight: 220, marginTop: 14 }}>
            <View style={{ backgroundColor: colors.bg, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: colors.border }}>
              <Text style={{ fontSize: 15, lineHeight: 21, color: colors.text }} {...tid('auto-text-body')}>{item.body || item.subtitle || 'No message text'}</Text>
              {item.has_media && <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 8 }}>Includes a photo or card image</Text>}
            </View>
          </ScrollView>

          <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
            <TouchableOpacity disabled={!!busy} onPress={() => run('cancel')} style={{ flex: 1, paddingVertical: 13, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,59,48,0.45)', alignItems: 'center' }} {...tid('auto-text-cancel')}>
              {busy === 'cancel' ? <ActivityIndicator color="#FF3B30" /> : <Text style={{ fontSize: 15, fontWeight: '700', color: '#FF3B30' }}>Skip this text</Text>}
            </TouchableOpacity>
            <TouchableOpacity disabled={!!busy} onPress={() => run('send')} style={{ flex: 1, paddingVertical: 13, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center' }} {...tid('auto-text-send-now')}>
              {busy === 'send' ? <ActivityIndicator color="#000" /> : <Text style={{ fontSize: 15, fontWeight: '700', color: '#000' }}>Send now</Text>}
            </TouchableOpacity>
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginTop: 10 }}>Skipping only removes this one text; the rest of the sequence keeps going.</Text>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
};
