import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { tid } from '../scripts/shared';
import { GOLD, UpcomingItem, kindVisual } from './types';

type Props = {
  item: UpcomingItem;
  onOpenContact: (item: UpcomingItem) => void;
  onPreview?: (item: UpcomingItem) => void;
  last?: boolean;
};

export const UpcomingRow = ({ item, onOpenContact, onPreview, last }: Props) => {
  const { colors } = useThemeStore();
  const v = kindVisual(item);
  const jessi = item.owner === 'jessi';
  const isText = item.kind === 'auto_text' || item.kind === 'manual_text';
  const who = item.contact_name || item.contact_phone || 'No name yet';
  const timeLabel = item.time || (item.kind === 'date' ? 'All day' : '');
  const dateNote = item.kind === 'date' ? (item.handled ? 'Jessi sends the card' : 'Not enrolled, text them') : null;
  return (
    <TouchableOpacity
      onPress={() => onOpenContact(item)}
      activeOpacity={0.75}
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, paddingHorizontal: 14,
        borderBottomWidth: last ? 0 : 0.5, borderBottomColor: colors.border, opacity: jessi ? 0.82 : 1,
      }}
      {...tid(`upcoming-row-${item.id}`)}
    >
      <View style={{ width: 62, alignItems: 'flex-start' }}>
        <Text numberOfLines={1} style={{ fontSize: 12, fontWeight: '700', color: timeLabel === 'All day' ? colors.textSecondary : colors.text }}>{timeLabel}</Text>
        <View style={{ marginTop: 3, paddingHorizontal: 6, paddingVertical: 1, borderRadius: 6, backgroundColor: jessi ? 'rgba(201,169,98,0.14)' : 'rgba(90,200,250,0.14)' }}>
          <Text style={{ fontSize: 10, fontWeight: '700', color: jessi ? GOLD : '#5AC8FA', letterSpacing: 0.4 }} {...tid(`upcoming-owner-${item.id}`)}>{jessi ? 'JESSI' : 'YOU'}</Text>
        </View>
      </View>
      <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: v.color + '22', alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={v.icon as any} size={16} color={v.color} />
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }} numberOfLines={1} {...tid(`upcoming-contact-${item.id}`)}>{who}</Text>
        <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
          {item.title}{dateNote ? ` · ${dateNote}` : ''}
        </Text>
        {!!item.subtitle && !isText && item.kind !== 'date' && (
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1, opacity: 0.8 }} numberOfLines={1}>{item.subtitle}</Text>
        )}
      </View>
      {isText && onPreview ? (
        <TouchableOpacity onPress={() => onPreview(item)} hitSlop={8} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: colors.border }} {...tid(`upcoming-preview-${item.id}`)}>
          <Text style={{ fontSize: 12, fontWeight: '600', color: GOLD }}>Preview</Text>
        </TouchableOpacity>
      ) : (
        <Ionicons name="chevron-forward" size={16} color="#48484A" />
      )}
    </TouchableOpacity>
  );
};
