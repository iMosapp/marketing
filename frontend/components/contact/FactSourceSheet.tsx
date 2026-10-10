/**
 * FactSourceSheet — "why we think this": the record behind one belief (excerpt, when, who, where to open it),
 * with Confirm / Not right for people allowed to verify. Opened from the Now strip, the Snapshot and milestone rows.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ActivityIndicator, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { intelAPI } from '../../services/api';

const GOLD = '#C9A962';
const KIND_ICON: Record<string, string> = { message: 'chatbubble', call: 'call', voice_memo: 'mic', lead_form: 'globe', sale: 'car-sport', appraisal: 'speedometer', rep: 'person', import: 'document-text', appointment: 'calendar', ai_inference: 'sparkles' };

function when(iso?: string | null) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function FactSourceSheet({ factId, colors, canVerify, onClose, onChanged }: { factId: string | null; colors: any; canVerify?: boolean; onClose: () => void; onChanged?: () => void }) {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState<'confirm' | 'dispute' | null>(null);
  const [done, setDone] = useState<string>('');

  useEffect(() => {
    setData(null); setDone(''); setBusy(null);
    if (!factId) return;
    let alive = true;
    intelAPI.source(factId).then(d => { if (alive) setData(d); }).catch(() => { if (alive) setData({ error: true }); });
    return () => { alive = false; };
  }, [factId]);

  const act = async (kind: 'confirm' | 'dispute') => {
    if (!factId || busy) return;
    setBusy(kind);
    try {
      await (kind === 'confirm' ? intelAPI.confirm(factId) : intelAPI.dispute(factId, 'Marked as not right from the contact screen'));
      setDone(kind === 'confirm' ? 'Confirmed. Thanks, that makes the picture sharper.' : 'Noted. It no longer counts as current; the record is kept.');
      onChanged?.();
    } catch {
      setDone('Could not save that. Try again in a moment.');
    } finally {
      setBusy(null);
    }
  };

  const open = () => {
    if (!data?.link) return;
    onClose();
    setTimeout(() => router.push(data.link), 150);
  };

  return (
    <Modal visible={!!factId} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} onPress={onClose} testID="fact-source-backdrop">
        <Pressable onPress={() => {}} style={{ backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, paddingBottom: 30, borderTopWidth: 1, borderColor: `${GOLD}55` }} testID="fact-source-sheet" dataSet={{ testid: 'fact-source-sheet' } as any}>
          <View style={{ alignSelf: 'center', width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border, marginBottom: 14 }} />
          {!data ? (
            <ActivityIndicator color={GOLD} style={{ marginVertical: 24 }} />
          ) : data.error ? (
            <Text style={{ color: colors.textSecondary, textAlign: 'center', paddingVertical: 20 }}>Could not load the source.</Text>
          ) : (
            <>
              <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>Why we think this</Text>
              <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text, lineHeight: 23 }} testID="fact-source-statement" dataSet={{ testid: 'fact-source-statement' } as any}>{data.statement}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12 }}>
                <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={(KIND_ICON[data.kind] || 'help') as any} size={15} color={GOLD} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} testID="fact-source-title" dataSet={{ testid: 'fact-source-title' } as any}>{data.title}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{[when(data.at), data.who ? `by ${data.who}` : '', data.confirmed ? 'confirmed' : 'not confirmed by anyone yet'].filter(Boolean).join(' · ')}</Text>
                </View>
              </View>
              {!!data.excerpt && (
                <View style={{ marginTop: 12, padding: 12, borderRadius: 12, backgroundColor: colors.surface, borderLeftWidth: 3, borderLeftColor: GOLD }}>
                  <Text style={{ fontSize: 14, lineHeight: 20, color: colors.text, fontStyle: 'italic' }} numberOfLines={8} testID="fact-source-excerpt" dataSet={{ testid: 'fact-source-excerpt' } as any}>“{data.excerpt}”</Text>
                </View>
              )}
              {data.evidence_count > 1 && (
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 8 }}>Seen {data.evidence_count} times{data.other_sources?.length ? ` (also via ${data.other_sources.join(', ').toLowerCase()})` : ''}.</Text>
              )}
              {!!done && <Text style={{ fontSize: 13, color: GOLD, marginTop: 12, fontWeight: '600' }} testID="fact-source-done" dataSet={{ testid: 'fact-source-done' } as any}>{done}</Text>}
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
                {!!data.link && (
                  <TouchableOpacity onPress={open} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 12, backgroundColor: GOLD }} testID="fact-source-open" dataSet={{ testid: 'fact-source-open' } as any}>
                    <Ionicons name="open-outline" size={15} color="#111" />
                    <Text style={{ fontSize: 13.5, fontWeight: '800', color: '#111' }}>Open source</Text>
                  </TouchableOpacity>
                )}
                {canVerify && !done && data.status !== 'disputed' && (
                  <>
                    {!data.confirmed && (
                      <TouchableOpacity onPress={() => act('confirm')} disabled={!!busy} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 12, borderWidth: 1, borderColor: '#34C759', backgroundColor: '#34C75918' }} testID="fact-source-confirm" dataSet={{ testid: 'fact-source-confirm' } as any}>
                        {busy === 'confirm' ? <ActivityIndicator size="small" color="#34C759" /> : <Ionicons name="checkmark-circle" size={15} color="#34C759" />}
                        <Text style={{ fontSize: 13.5, fontWeight: '800', color: '#34C759' }}>Confirm</Text>
                      </TouchableOpacity>
                    )}
                    <TouchableOpacity onPress={() => act('dispute')} disabled={!!busy} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface }} testID="fact-source-dispute" dataSet={{ testid: 'fact-source-dispute' } as any}>
                      {busy === 'dispute' ? <ActivityIndicator size="small" color={colors.textSecondary} /> : <Ionicons name="close-circle" size={15} color={colors.textSecondary} />}
                      <Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.textSecondary }}>Not right</Text>
                    </TouchableOpacity>
                  </>
                )}
              </View>
            </>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
}
