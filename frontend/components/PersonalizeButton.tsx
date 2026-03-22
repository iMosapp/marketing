import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, FlatList, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const MERGE_TAGS = [
  { key: '{first_name}', label: 'First Name', icon: 'person-outline' },
  { key: '{last_name}', label: 'Last Name', icon: 'person-outline' },
  { key: '{full_name}', label: 'Full Name', icon: 'people-outline' },
  { key: '{phone}', label: 'Phone', icon: 'call-outline' },
  { key: '{email}', label: 'Email', icon: 'mail-outline' },
  { key: '{my_name}', label: 'My Name', icon: 'person-circle-outline' },
  { key: '{my_phone}', label: 'My Phone', icon: 'phone-portrait-outline' },
  { key: '{company}', label: 'Company', icon: 'business-outline' },
  { key: '{date_sold}', label: 'Date Sold', icon: 'calendar-outline' },
];

interface Props {
  onInsert: (tag: string) => void;
  colors: any;
  compact?: boolean; // smaller icon-only mode for toolbars
}

export function PersonalizeButton({ onInsert, colors, compact }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <TouchableOpacity
        onPress={() => setOpen(true)}
        style={compact ? s.compactBtn : [s.btn, { borderColor: colors.border, backgroundColor: colors.card }]}
        data-testid="personalize-btn"
      >
        <Ionicons name="at-outline" size={compact ? 22 : 16} color={compact ? '#C9A962' : '#C9A962'} />
        {!compact && <Text style={s.btnText}>Personalize</Text>}
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity style={s.overlay} activeOpacity={1} onPress={() => setOpen(false)}>
          <View style={[s.sheet, { backgroundColor: colors.card }]} onStartShouldSetResponder={() => true}>
            <View style={s.sheetHeader}>
              <Text style={[s.sheetTitle, { color: colors.text }]}>Insert Personalization</Text>
              <TouchableOpacity onPress={() => setOpen(false)} data-testid="personalize-close">
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <Text style={[s.sheetSub, { color: colors.textSecondary }]}>
              Tap a field to insert it into your message. It will be replaced with the contact's real data when sent.
            </Text>
            <FlatList
              data={MERGE_TAGS}
              keyExtractor={(item) => item.key}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[s.tagRow, { borderBottomColor: colors.border }]}
                  onPress={() => { onInsert(item.key); setOpen(false); }}
                  data-testid={`merge-tag-${item.key.replace(/[{}]/g, '')}`}
                >
                  <View style={s.tagIcon}>
                    <Ionicons name={item.icon as any} size={18} color="#C9A962" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[s.tagLabel, { color: colors.text }]}>{item.label}</Text>
                    <Text style={[s.tagKey, { color: colors.textSecondary }]}>{item.key}</Text>
                  </View>
                  <View style={s.pill}>
                    <Text style={s.pillText}>{item.label}</Text>
                  </View>
                </TouchableOpacity>
              )}
            />
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  btn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, borderWidth: 1,
  },
  btnText: { fontSize: 15, fontWeight: '600', color: '#C9A962' },
  compactBtn: { padding: 4 },
  overlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end',
  },
  sheet: {
    borderTopLeftRadius: 16, borderTopRightRadius: 16,
    paddingBottom: 34, maxHeight: '70%',
  },
  sheetHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8,
  },
  sheetTitle: { fontSize: 18, fontWeight: '700' },
  sheetSub: { fontSize: 14, paddingHorizontal: 16, paddingBottom: 12 },
  tagRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  tagIcon: {
    width: 32, height: 32, borderRadius: 8, backgroundColor: 'rgba(201,169,98,0.15)',
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  tagLabel: { fontSize: 17, fontWeight: '500' },
  tagKey: { fontSize: 14, marginTop: 1 },
  pill: {
    backgroundColor: 'rgba(201,169,98,0.2)', borderRadius: 6,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  pillText: { fontSize: 13, fontWeight: '600', color: '#C9A962' },
});
