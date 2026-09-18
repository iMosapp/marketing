import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Label, Chip, GoldButton, fmtPhone, deptLabel, deptsOfClient, difficultyLabel, directionHint, DIFFICULTIES, tid, type Client, type Person, type Direction, type Difficulty } from './shared';

type Props = { person: Person | null; client: Client; colors: any; onClose: () => void; onStarted: () => void };

// "Shop now" on a person: pick who calls whom and how tough the shopper is, then the call goes out in seconds (business hours do not apply).
export const ShopNowSheet = ({ person, client, colors, onClose, onStarted }: Props) => {
  const { showToast } = useToast();
  const [direction, setDirection] = useState<Direction | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { if (person) { setDirection(null); setDifficulty(null); setError(''); } }, [person?.id]);
  const fallback = person?.difficulty || (client.difficulty && client.difficulty !== 'mixed' ? client.difficulty : 'medium');
  const first = (person?.name || '').split(' ')[0];

  const go = async () => {
    if (!person) return;
    setBusy(true); setError('');
    try {
      await api.post(`/shop-clients/${client.id}/calls/shop-now`, { target_id: person.id, ...(direction ? { direction } : {}), ...(difficulty ? { difficulty } : {}) });
      showToast(`Calling ${first} now`, 'success'); onClose(); onStarted();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || (!e?.response ? 'No connection to the server, try again in a moment' : 'Could not place the call');
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally { setBusy(false); }
  };

  return (
    <Sheet visible={!!person} onClose={onClose} title={person ? `Shop ${first} now` : 'Shop now'} colors={colors} testID="shop-now-sheet" error={error}
      footer={<GoldButton label={`Call ${first || 'them'} now`} onPress={go} busy={busy} icon="call" testID="shop-now-call" />}>
      {!!person && <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }} {...tid('shop-now-text')}>The AI {client.customer_noun || 'shopper'} calls {fmtPhone(person.phone)} in a few seconds with a {deptLabel(person.department, deptsOfClient(client)).toLowerCase()} challenge they have not had yet. Business hours don't apply; if they don't pick up or press 2, the shop waits for you to tap Try again.</Text>}
      <View style={{ gap: 6 }}>
        <Label t="WHO CALLS WHOM" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          <Chip label="Surprise me" active={!direction} onPress={() => setDirection(null)} colors={colors} testID="shop-now-direction-any" />
          <Chip label="Inbound" active={direction === 'inbound'} onPress={() => setDirection('inbound')} colors={colors} testID="shop-now-direction-inbound" />
          <Chip label="Outbound" active={direction === 'outbound'} onPress={() => setDirection('outbound')} colors={colors} testID="shop-now-direction-outbound" />
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>{direction ? directionHint(direction) : 'Inbound or outbound, whichever challenge comes up. Outbound: Jessi tells them the shopper left a lead and they are calling back.'}</Text>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="HOW TOUGH" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          <Chip label={`Usual (${difficultyLabel(fallback)})`} active={!difficulty} onPress={() => setDifficulty(null)} colors={colors} testID="shop-now-difficulty-default" />
          {DIFFICULTIES.map(d => <Chip key={d.key} label={d.label} active={difficulty === d.key} onPress={() => setDifficulty(d.key)} colors={colors} testID={`shop-now-difficulty-${d.key}`} />)}
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>{DIFFICULTIES.find(d => d.key === (difficulty || fallback))?.hint}</Text>
      </View>
    </Sheet>
  );
};
