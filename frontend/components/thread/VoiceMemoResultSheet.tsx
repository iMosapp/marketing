import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, Platform, ActivityIndicator, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';

const GOLD = '#C9A962';
const PURPLE = '#AF52DE';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, '0')}`;

const LABELS: Record<string, string> = {
  spouse_name: 'Spouse', spouse_details: 'About their spouse', kids: 'Kids', interests: 'Interests', occupation: 'Job', employer: 'Works at',
  vehicle_purchased: 'Vehicle', vehicle_color: 'Color', vehicle_details: 'Vehicle notes', trade_in: 'Trade-in', purchase_context: 'What matters to them',
  important_dates: 'Dates to remember', pets: 'Pets', favorite_restaurant: 'Favorite spot', neighborhood: 'Lives in', referral_potential: 'Referral',
  personal_notes: 'Worth remembering', communication_preference: 'Prefers',
};

const valueText = (k: string, v: any): string => {
  if (Array.isArray(v)) {
    if (k === 'kids') return v.map((x: any) => (typeof x === 'string' ? x : [x.name, x.details].filter(Boolean).join(', '))).join(' · ');
    if (k === 'important_dates') return v.map((x: any) => (typeof x === 'string' ? x : [x.date, x.description].filter(Boolean).join(': '))).join(' · ');
    return v.map(x => (typeof x === 'string' ? x : JSON.stringify(x))).join(', ');
  }
  return typeof v === 'string' ? v : JSON.stringify(v);
};

export type MemoNote = { id: string; transcript?: string; duration?: number; kind?: string };
type Props = { note: MemoNote | null; userId: string; contactId: string; contactFirst: string; colors: any; onClose: () => void; onProfilePage?: boolean };

// Shown right after a voice memo saves: the transcript, then (a few seconds later) what Jessi added to the profile and the follow-up it set.
export const VoiceMemoResultSheet = ({ note, userId, contactId, contactFirst, colors, onClose, onProfilePage }: Props) => {
  const router = useRouter();
  const [details, setDetails] = useState<Record<string, any> | null>(null);
  const [followup, setFollowup] = useState<{ id: string; title: string; due_date: string } | null>(null);
  const [done, setDone] = useState(false);
  const timer = useRef<any>(null);
  const textColor = colors.textPrimary || colors.text;

  useEffect(() => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
    setDetails(null); setFollowup(null); setDone(false);
    if (!note?.id) return;
    if (!note.transcript || note.transcript.trim().length < 10) { setDone(true); return; }
    let tries = 0;
    const poll = async () => {
      tries += 1;
      try {
        const res = await api.get(`/voice-notes/${userId}/${contactId}/${note.id}`);
        if (res.data.intelligence_done || tries >= 20) {
          setDetails(res.data.extracted_details || {}); setFollowup(res.data.followup_task || null); setDone(true);
          if (timer.current) { clearInterval(timer.current); timer.current = null; }
        }
      } catch { if (tries >= 20) { setDone(true); if (timer.current) clearInterval(timer.current); } }
    };
    timer.current = setInterval(poll, 2000);
    poll();
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [note?.id]);

  const rows = Object.entries(details || {}).filter(([k, v]) => LABELS[k] && v && (!Array.isArray(v) || v.length));
  const heard = !!note?.transcript && note.transcript.trim().length >= 10;

  return (
    <Modal visible={!!note} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={onClose} />
        <View style={{ backgroundColor: colors.background || colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, paddingBottom: Platform.OS === 'ios' ? 30 : 18, gap: 12, maxHeight: '85%' }} {...tid('memo-result')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Ionicons name="checkmark-circle" size={22} color="#34C759" />
            <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: textColor }} numberOfLines={1} {...tid('memo-result-title')}>Memo saved{note?.duration ? ` · ${fmt(note.duration)}` : ''}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('memo-result-close')}><Ionicons name="close" size={24} color={textColor} /></TouchableOpacity>
          </View>
          <ScrollView style={{ flexGrow: 0 }} contentContainerStyle={{ gap: 12 }}>
            <View style={{ backgroundColor: colors.surface || colors.card, borderRadius: 12, padding: 12 }} {...tid('memo-result-transcript')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 6 }}>WHAT YOU SAID</Text>
              <Text style={{ fontSize: 14.5, color: heard ? textColor : colors.textSecondary, lineHeight: 21, fontStyle: heard ? 'normal' : 'italic' }}>
                {heard ? note!.transcript : 'Nothing came through clearly. The audio is saved on the profile, try again a little closer to the mic.'}
              </Text>
            </View>

            {heard && (
              <View style={{ backgroundColor: PURPLE + '14', borderLeftWidth: 3, borderLeftColor: PURPLE, borderRadius: 12, padding: 12, gap: 8 }} {...tid('memo-result-intel')}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: PURPLE, letterSpacing: 1 }}>ADDED TO {contactFirst.toUpperCase()}'S PROFILE</Text>
                {!done ? (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('memo-result-intel-loading')}>
                    <ActivityIndicator size="small" color={PURPLE} /><Text style={{ fontSize: 13, color: colors.textSecondary }}>Jessi is pulling out the details…</Text>
                  </View>
                ) : rows.length === 0 ? (
                  <Text style={{ fontSize: 13, color: colors.textSecondary, fontStyle: 'italic' }} {...tid('memo-result-intel-empty')}>No new personal details this time. The memo is saved and Jessi can still cite it.</Text>
                ) : rows.map(([k, v]) => (
                  <View key={k} style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }} {...tid(`memo-result-intel-${k}`)}>
                    <Text style={{ fontSize: 13, fontWeight: '800', color: textColor, minWidth: 96 }}>{LABELS[k]}</Text>
                    <Text style={{ flex: 1, fontSize: 13.5, color: textColor, lineHeight: 19 }}>{valueText(k, v)}</Text>
                  </View>
                ))}
              </View>
            )}

            {followup && (
              <TouchableOpacity onPress={() => { onClose(); router.push('/touchpoints' as any); }} style={{ backgroundColor: colors.surface || colors.card, borderRadius: 12, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('memo-result-followup')}>
                <Ionicons name="checkbox-outline" size={18} color={GOLD} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>FOLLOW-UP ADDED</Text>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: textColor, marginTop: 2 }}>{followup.title}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>Due {new Date(followup.due_date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
          </ScrollView>
          <TouchableOpacity onPress={() => { onClose(); if (!onProfilePage) router.push(`/contact/${contactId}` as any); }} style={{ height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('memo-result-profile')}>
            <Ionicons name={onProfilePage ? 'checkmark' : 'person'} size={16} color="#111" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>{onProfilePage ? 'Done' : `View ${contactFirst}'s profile`}</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};
