import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, GOLD, tid, type Disposition, type Lead, type Attempt } from './shared';

const CALLBACK_CHOICES = [{ label: 'In 2 hours', h: 2 }, { label: 'Tomorrow', h: 24 }, { label: 'In 3 days', h: 72 }, { label: 'Next week', h: 168 }];

// After a call: one tap for the outcome, optional notes, callback timing. Interested / Call back also create the contact in the rep's book.
export const DispositionSheet = ({ visible, onClose, colors, sessionId, attempt, lead, dispositions, onDone }: { visible: boolean; onClose: () => void; colors: any; sessionId: string; attempt: Attempt | null; lead: Lead | null; dispositions: Disposition[]; onDone: () => void }) => {
  const { showToast } = useToast();
  const [key, setKey] = useState('');
  const [notes, setNotes] = useState('');
  const [cbHours, setCbHours] = useState(24);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (visible) { setKey(attempt?.status === 'voicemail' ? 'voicemail' : ''); setNotes(''); setCbHours(24); } }, [visible, attempt?.id]);

  const save = async () => {
    if (!key) { showToast('Pick an outcome', 'error'); return; }
    setBusy(true);
    try {
      const callback_at = key === 'callback' ? new Date(Date.now() + cbHours * 3600 * 1000).toISOString() : undefined;
      await api.post(`/dialer/sessions/${sessionId}/disposition`, { attempt_id: attempt?.id, disposition: key, notes, callback_at });
      onDone(); onClose();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };
  const d = dispositions.find(x => x.key === key);

  return (
    <Sheet visible={visible} onClose={onClose} title={lead ? `How did it go with ${lead.first_name || lead.name}?` : 'How did it go?'} colors={colors} testID="disposition-sheet"
      footer={<GoldButton label={d?.promote ? `Save · adds ${lead?.first_name || 'them'} to your contacts` : 'Save outcome'} onPress={save} busy={busy} disabled={!key} testID="disposition-save" icon="checkmark" />}>
      {!!lead && <Text style={{ fontSize: 13, color: colors.textSecondary }}>{[lead.company, lead.phone, lead.state].filter(Boolean).join(' · ')}</Text>}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {dispositions.map(x => {
          const on = key === x.key;
          return (
            <TouchableOpacity key={x.key} onPress={() => setKey(x.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 40, borderRadius: 20, backgroundColor: on ? x.color : colors.card, borderWidth: 1, borderColor: on ? x.color : colors.border }} {...tid(`disposition-${x.key}`)}>
              <Ionicons name={x.icon as any} size={15} color={on ? '#111' : x.color} />
              <Text style={{ fontSize: 13.5, fontWeight: '800', color: on ? '#111' : colors.text }}>{x.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      {key === 'callback' && (
        <View style={{ gap: 6 }}>
          <Label t="WHEN" colors={colors} />
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {CALLBACK_CHOICES.map(c => <Chip key={c.h} label={c.label} small active={cbHours === c.h} onPress={() => setCbHours(c.h)} colors={colors} testID={`disposition-cb-${c.h}`} />)}
          </View>
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Goes on your Touchpoints as a task and back into this list at that time.</Text>
        </View>
      )}
      {key === 'dnc' && <Text style={{ fontSize: 12.5, color: '#FF3B30', lineHeight: 17 }} {...tid('disposition-dnc-note')}>Added to the Do Not Call list for good. Every campaign skips this number from now on.</Text>}
      <Field label="NOTES (OPTIONAL)" value={notes} onChange={setNotes} colors={colors} multiline placeholder="What they said, what to send them, best time to reach…" testID="disposition-notes" />
    </Sheet>
  );
};
