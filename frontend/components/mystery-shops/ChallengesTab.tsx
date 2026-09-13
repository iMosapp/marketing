import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { ChallengeEditorSheet } from './ChallengeEditorSheet';
import { ChallengeDetailSheet, ChallengeGroups } from './ChallengeDetailSheet';
import { GeneratorSheet } from './GeneratorSheet';
import { GOLD, PURPLE, tid, type Challenge, type ChallengeDraft, type Client } from './shared';

// The challenge pool for one client: global library scenarios + scenarios written for this client only.
export const ChallengesTab = ({ client, colors }: { client: Client; colors: any }) => {
  const { showToast } = useToast();
  const [rows, setRows] = useState<Challenge[] | null>(null);
  const [open, setOpen] = useState<Challenge | null>(null);
  const [editor, setEditor] = useState<null | { existing?: Challenge; draft?: ChallengeDraft }>(null);
  const [generator, setGenerator] = useState(false);
  const scope = { clientId: client.id, clientName: client.name };

  const load = async () => { try { const r = await api.get(`/shop-clients/${client.id}/challenges`); setRows(r.data.challenges); } catch { setRows([]); } };
  useEffect(() => { load(); }, [client.id]);

  const remove = (c: Challenge) => showConfirm(c.client_specific ? 'Delete this challenge?' : 'Hide this global challenge?', c.client_specific ? 'Only this client had it.' : 'It disappears from every client\'s pool.', async () => {
    try { await api.delete(`/shop-clients/challenges/${c.id}`); setOpen(null); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, c.client_specific ? 'Delete' : 'Hide');

  return (
    <View style={{ gap: 16 }}>
      <TouchableOpacity onPress={() => setGenerator(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: GOLD + '1A', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('challenge-generate')}>
        <Ionicons name="sparkles" size={20} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Describe a scenario, Jessi writes the challenge</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Sales, service, parts or rental. Save it to the library or just for {client.name}.</Text></View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      <TouchableOpacity onPress={() => setEditor({})} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('challenge-add')}>
        <Ionicons name="create-outline" size={18} color={PURPLE} />
        <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>Write one by hand or paste a script</Text>
        <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Every shop picks a challenge the person has not had yet, fills in one of the client's vehicles, and adds 0 to 2 random curveballs. Once someone has had them all, the rotation starts over with the oldest.</Text>
      <ChallengeGroups rows={rows} colors={colors} onOpen={setOpen} emptyHint="Nothing in the library for this department yet. Have Jessi write one above." />
      <ChallengeDetailSheet open={open} onClose={() => setOpen(null)} colors={colors} onEdit={(c) => { setOpen(null); setEditor({ existing: c }); }} onDelete={remove} />
      <ChallengeEditorSheet visible={!!editor} onClose={() => setEditor(null)} colors={colors} existing={editor?.existing} initial={editor?.draft} scope={scope} onSaved={load} />
      <GeneratorSheet visible={generator} onClose={() => setGenerator(false)} colors={colors} scope={scope} onSaved={load} onEditDraft={(d) => { setGenerator(false); setEditor({ draft: d }); }} />
    </View>
  );
};
