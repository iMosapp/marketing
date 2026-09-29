import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Chip, GOLD, GREEN, RED, tid, type Challenge } from './shared';

const DIFF = [{ key: 'easy', label: 'Easy' }, { key: 'medium', label: 'Medium' }, { key: 'hard', label: 'Hard' }];
const fmtPhone = (p: string) => { const d = p.replace(/\D/g, ''); const n = d.length === 11 && d.startsWith('1') ? d.slice(1) : d; return n.length === 10 ? `(${n.slice(0, 3)}) ${n.slice(3, 6)}-${n.slice(6)}` : p; };

// Audition a challenge on yourself: one tap and the shopper rings your cell with exactly this scenario, graded like a real shop.
// The number is remembered; the result lands in the Quick shops bucket flagged as a preview.
export const ChallengePreviewCall = ({ challenge, colors, onClose }: { challenge: Challenge; colors: any; onClose: () => void }) => {
  const router = useRouter();
  const { showToast } = useToast();
  const [phone, setPhone] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [difficulty, setDifficulty] = useState('medium');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ phone: string; client_id: string } | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { api.get('/shop-clients/challenges/preview-phone').then(r => { setPhone(r.data.phone || ''); if (!r.data.phone) setEditing(true); }).catch(() => setPhone('')); }, []);
  useEffect(() => { setDone(null); setErr(''); }, [challenge.id]);

  const call = async () => {
    setBusy(true); setErr('');
    try {
      const r = await api.post(`/shop-clients/challenges/${challenge.id}/preview-call`, { phone: editing ? draft : undefined, difficulty }, { timeout: 60000 });
      setPhone(r.data.phone); setEditing(false); setDone({ phone: r.data.phone, client_id: r.data.client_id });
    } catch (e: any) { setErr(e?.response?.data?.detail || 'Could not place the call'); }
    finally { setBusy(false); }
  };

  if (done) {
    return (
      <View style={{ gap: 8, backgroundColor: GREEN + '14', borderRadius: 14, padding: 12, borderWidth: 1, borderColor: GREEN + '66' }} {...tid('preview-call-done')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Ionicons name="call" size={18} color={GREEN} /><Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: colors.text }}>Ringing {fmtPhone(done.phone)} now. Pick up and play the rep.</Text></View>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{challenge.persona?.name || 'The shopper'} opens with "{challenge.persona?.opening_line}". Your graded scorecard texts you when you hang up; the call lands in Quick shops marked as a preview.</Text>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TouchableOpacity onPress={() => { onClose(); router.push(`/admin/mystery-shops/${done.client_id}` as any); }} style={{ flex: 1, height: 38, borderRadius: 12, backgroundColor: GREEN, alignItems: 'center', justifyContent: 'center' }} {...tid('preview-call-open')}><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Open Quick shops</Text></TouchableOpacity>
          <TouchableOpacity onPress={() => setDone(null)} style={{ height: 38, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('preview-call-again')}><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Call again</Text></TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={{ gap: 8, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('preview-call-panel')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="headset" size={16} color={GOLD} />
        <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '800', color: colors.text }}>Audition it yourself</Text>
        <View style={{ flexDirection: 'row', gap: 4 }}>{DIFF.map(d => <Chip key={d.key} label={d.label} small active={difficulty === d.key} onPress={() => setDifficulty(d.key)} colors={colors} testID={`preview-call-diff-${d.key}`} />)}</View>
      </View>
      {phone === null ? <ActivityIndicator color={GOLD} /> : editing ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <TextInput value={draft} onChangeText={setDraft} placeholder="Your cell, e.g. 555 123 4567" placeholderTextColor={colors.textSecondary} keyboardType="phone-pad" autoFocus={!phone}
            style={{ flex: 1, height: 40, borderRadius: 10, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg, paddingHorizontal: 12, color: colors.text, fontSize: 15 }} {...tid('preview-call-phone')} />
          {!!phone && <TouchableOpacity onPress={() => setEditing(false)} hitSlop={8} {...tid('preview-call-phone-cancel')}><Ionicons name="close" size={20} color={colors.textSecondary} /></TouchableOpacity>}
        </View>
      ) : (
        <TouchableOpacity onPress={() => { setDraft(''); setEditing(true); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('preview-call-phone-edit')}>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Rings <Text style={{ fontWeight: '800', color: colors.text }}>{fmtPhone(phone)}</Text></Text><Ionicons name="pencil" size={12} color={GOLD} />
        </TouchableOpacity>
      )}
      {!!err && <Text style={{ fontSize: 12.5, color: RED }} {...tid('preview-call-error')}>{err}</Text>}
      <TouchableOpacity onPress={call} disabled={busy || phone === null || (editing && draft.replace(/\D/g, '').length < 10)} style={{ height: 44, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: busy || (editing && draft.replace(/\D/g, '').length < 10) ? 0.6 : 1 }} {...tid('preview-call-go')}>
        {busy ? <ActivityIndicator color="#111" /> : <Ionicons name="call" size={18} color="#111" />}
        <Text style={{ fontSize: 14.5, fontWeight: '900', color: '#111' }}>{busy ? 'Dialing…' : 'Call me with this one'}</Text>
      </TouchableOpacity>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }}>Real call, graded like a real shop, scorecard texted after. It never counts toward a client.</Text>
    </View>
  );
};
