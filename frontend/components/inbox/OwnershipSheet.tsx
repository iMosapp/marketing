import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Avatar } from '../Avatar';
import { GOLD, tid, Ownership, RepCard, ownershipAPI, errText, fmtPhone, firstName, timeAgo } from './ownership';
import { RepPicker, InboxPicker, NoteConfirm } from './OwnershipPickers';

type Mode = 'main' | 'assign' | 'share' | 'move' | 'release' | 'graduate';

type Props = {
  visible: boolean;
  conversationId: string | null;
  meId?: string;
  colors: any;
  onClose: () => void;
  onChanged?: () => void;
  showToast?: (msg: string, type?: any, ms?: number) => void;
  aiModeLabel?: string;
  onChangeAi?: () => void;
};

const Eyebrow = ({ children, colors }: { children: React.ReactNode; colors: any }) => (
  <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 8 }}>{children}</Text>
);

const ActionRow = ({ icon, label, sub, onPress, colors, testId, color }: { icon: any; label: string; sub?: string; onPress: () => void; colors: any; testId: string; color?: string }) => (
  <TouchableOpacity onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 12, borderRadius: 12, backgroundColor: colors.card }} {...tid(testId)}>
    <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: (color || GOLD) + '22', alignItems: 'center', justifyContent: 'center' }}>
      <Ionicons name={icon} size={17} color={color || GOLD} />
    </View>
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{label}</Text>
      {sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{sub}</Text> : null}
    </View>
    <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
  </TouchableOpacity>
);

const historyLine = (h: any) => {
  const who = firstName(h.by_name) || 'Someone';
  if (h.kind === 'claim') return h.by && h.to && h.by !== h.to ? `${who} assigned this to ${firstName(h.to_name)}` : `${firstName(h.to_name)} picked this up`;
  if (h.kind === 'reassign') return `${who} handed this from ${h.from_name ? firstName(h.from_name) : 'the queue'} to ${firstName(h.to_name)}`;
  if (h.kind === 'release') return `${who} released it back to the inbox`;
  if (h.kind === 'move') return `${who} moved it to another inbox`;
  if (h.kind === 'graduate') return `Moved to ${firstName(h.to_name)}'s direct line`;
  return `${who}: ${h.kind}`;
};

export function OwnershipSheet({ visible, conversationId, meId, colors, onClose, onChanged, showToast, aiModeLabel, onChangeAi }: Props) {
  const [data, setData] = useState<Ownership | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<Mode>('main');
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!conversationId) return;
    setLoading(true);
    try { setData(await ownershipAPI.get(conversationId)); }
    catch (e) { showToast?.(errText(e, "Couldn't load who's on this"), 'error'); }
    finally { setLoading(false); }
  }, [conversationId]);

  useEffect(() => { if (visible) { setMode('main'); load(); } }, [visible, load]);

  const run = async (key: string, fn: () => Promise<any>, ok: string) => {
    if (!conversationId) return;
    setBusy(key);
    try {
      await fn();
      showToast?.(ok, 'success', 2000);
      await load();
      setMode('main');
      onChanged?.();
    } catch (e) { showToast?.(errText(e), 'error', 3000); }
    finally { setBusy(null); }
  };

  if (!visible) return null;
  const c = colors;
  const inbox = data?.inbox;
  const owner = data?.owner;
  const isMine = !!owner && owner.id === meId;
  const can = data?.can;

  const body = () => {
    if (!data) return <ActivityIndicator color={GOLD} style={{ paddingVertical: 30 }} />;
    if (mode === 'assign') return (
      <RepPicker title={owner ? 'Hand this to' : 'Assign to'} sub={inbox ? `Anyone on the ${inbox.name} inbox` : 'A teammate in your store'} confirmLabel={owner ? 'Hand to' : 'Assign to'}
        reps={inbox ? data.members : null} excludeIds={owner ? [owner.id] : []} meId={meId} onBack={() => setMode('main')} colors={c} testId="own-assign"
        onConfirm={(rep, note) => run('assign', () => ownershipAPI.assign(conversationId!, rep.id, note), `Handed to ${firstName(rep.name)}`)} />
    );
    if (mode === 'share') return (
      <RepPicker title="Share with a teammate" sub="They can read and reply. They only get pinged when you're off shift or quiet for 15 min." confirmLabel="Share with"
        reps={null} excludeIds={[...(owner ? [owner.id] : []), ...data.collaborators.map(x => x.id)]} meId={meId} withNote={false} onBack={() => setMode('main')} colors={c} testId="own-share"
        onConfirm={(rep) => run('share', () => ownershipAPI.collaborator(conversationId!, rep.id, true), `Shared with ${firstName(rep.name)}`)} />
    );
    if (mode === 'move') return (
      <InboxPicker inboxes={data.inboxes} currentId={inbox?.id} onBack={() => setMode('main')} colors={c} testId="own-move"
        onConfirm={(ib, rep, note) => run('move', () => ownershipAPI.move(conversationId!, ib.id, rep?.id || null, note), `Moved to ${ib.name}`)} />
    );
    if (mode === 'release') return (
      <NoteConfirm title={`Release to ${inbox?.name || 'the inbox'}`} sub="Puts it back up for grabs. The team gets a ping." confirmLabel="Release it" onBack={() => setMode('main')} colors={c} testId="own-release"
        placeholder="Leave the next rep a note (optional)" onConfirm={(note) => run('release', () => ownershipAPI.release(conversationId!, note), 'Released to the team')} />
    );
    if (mode === 'graduate') return (
      <NoteConfirm title={`Move to ${firstName(owner?.name)}'s direct line`} sub={`The customer gets a short text from ${firstName(owner?.name)}'s own number and every reply lands there from now on.`}
        confirmLabel="Move it" onBack={() => setMode('main')} colors={c} testId="own-graduate" placeholder={null as any}
        onConfirm={() => run('graduate', () => ownershipAPI.graduate(conversationId!), `Now on ${firstName(owner?.name)}'s line`)} />
    );
    return (
      <View style={{ gap: 20 }}>
        {/* Where it lives */}
        <View>
          <Eyebrow colors={c}>LIVES IN</Eyebrow>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: c.card }} {...tid('own-lives-in')}>
            <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: inbox ? (inbox.color || GOLD) : '#8E8E93' }} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: c.text }}>{inbox ? `${inbox.name} inbox` : owner ? `${isMine ? 'Your' : firstName(owner.name) + "'s"} personal line` : 'Personal line'}</Text>
              <Text style={{ fontSize: 12, color: c.textSecondary, marginTop: 1 }}>
                {data.from_number ? `Texts go out from ${fmtPhone(data.from_number)}` : 'No sending number yet'}
                {data.graduated && data.graduated_from ? ` · came from ${data.graduated_from.name}` : ''}
              </Text>
            </View>
          </View>
        </View>

        {/* Owner */}
        <View>
          <Eyebrow colors={c}>WHO HAS IT</Eyebrow>
          {owner ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, backgroundColor: c.card }} {...tid('own-owner')}>
              <Avatar photo={owner.photo || null} name={owner.name} size="md" />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: c.text }}>{owner.name}{isMine ? ' (you)' : ''}</Text>
                <Text style={{ fontSize: 12, color: c.textSecondary, marginTop: 1 }}>{owner.role ? String(owner.role).replace('_', ' ') : 'Owner'} · gets every alert</Text>
              </View>
              {can?.assign && (
                <TouchableOpacity onPress={() => setMode('assign')} style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, backgroundColor: GOLD + '22', borderWidth: 1, borderColor: GOLD }} {...tid('own-hand-off-btn')}>
                  <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>Hand off</Text>
                </TouchableOpacity>
              )}
            </View>
          ) : (
            <View style={{ padding: 12, borderRadius: 12, backgroundColor: GOLD + '18', borderWidth: 1, borderColor: GOLD + '55', gap: 10 }} {...tid('own-unassigned')}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name="hand-left" size={16} color={GOLD} />
                <Text style={{ fontSize: 14, fontWeight: '800', color: c.text }}>Up for grabs</Text>
                <Text style={{ fontSize: 12, color: c.textSecondary }}>· nobody owns this yet</Text>
              </View>
              {data.handoff_note?.text ? <Text style={{ fontSize: 13, color: c.text, fontStyle: 'italic' }}>"{data.handoff_note.text}" - {data.handoff_note.by_name}</Text> : null}
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {can?.claim && (
                  <TouchableOpacity onPress={() => run('claim', () => ownershipAPI.claim(conversationId!), "It's yours")} disabled={busy === 'claim'} style={{ flex: 1, height: 42, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: busy === 'claim' ? 0.6 : 1 }} {...tid('own-claim-btn')}>
                    <Ionicons name="hand-right" size={16} color="#111" />
                    <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>I've got it</Text>
                  </TouchableOpacity>
                )}
                {can?.assign && (
                  <TouchableOpacity onPress={() => setMode('assign')} style={{ flex: 1, height: 42, borderRadius: 12, backgroundColor: c.card, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('own-assign-btn')}>
                    <Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>Give to someone</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          )}
        </View>

        {/* Collaborators */}
        <View>
          <Eyebrow colors={c}>ALSO ON THIS THREAD</Eyebrow>
          <View style={{ gap: 6 }}>
            {data.collaborators.length === 0 && <Text style={{ fontSize: 13, color: c.textSecondary }} {...tid('own-no-collabs')}>Just the owner for now.</Text>}
            {data.collaborators.map(rep => (
              <View key={rep.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 12, backgroundColor: c.card }} {...tid(`own-collab-${rep.id}`)}>
                <Avatar photo={rep.photo || null} name={rep.name} size="sm" />
                <Text style={{ flex: 1, fontSize: 14, fontWeight: '600', color: c.text }}>{rep.name}{rep.id === meId ? ' (you)' : ''}</Text>
                {can?.share && (
                  <TouchableOpacity onPress={() => run(`unshare-${rep.id}`, () => ownershipAPI.collaborator(conversationId!, rep.id, false), `${firstName(rep.name)} removed`)} hitSlop={8} {...tid(`own-collab-remove-${rep.id}`)}>
                    <Ionicons name="close-circle" size={20} color={c.textSecondary} />
                  </TouchableOpacity>
                )}
              </View>
            ))}
            {can?.share && (
              <TouchableOpacity onPress={() => setMode('share')} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, paddingHorizontal: 12 }} {...tid('own-share-btn')}>
                <Ionicons name="person-add" size={16} color={GOLD} />
                <Text style={{ fontSize: 14, fontWeight: '700', color: GOLD }}>Share with a teammate</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Jessi */}
        {aiModeLabel ? (
          <View>
            <Eyebrow colors={c}>JESSI</Eyebrow>
            <TouchableOpacity onPress={onChangeAi} disabled={!onChangeAi} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, backgroundColor: c.card }} {...tid('own-jessi-row')}>
              <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: '#34C75922', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="sparkles" size={17} color="#34C759" />
              </View>
              <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: c.text }}>{aiModeLabel}</Text>
              {onChangeAi ? <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Change</Text> : null}
            </TouchableOpacity>
          </View>
        ) : null}

        {/* Actions */}
        {(can?.move || can?.release || can?.graduate) && (
          <View>
            <Eyebrow colors={c}>MOVE IT</Eyebrow>
            <View style={{ gap: 6 }}>
              {can?.release && <ActionRow icon="arrow-undo" label={`Release to ${inbox?.name}`} sub="Back up for grabs for the whole team" onPress={() => setMode('release')} colors={c} testId="own-release-btn" color="#FF9500" />}
              {can?.move && <ActionRow icon="swap-horizontal" label="Move to another inbox" sub={inbox ? 'Sales to Service, and so on' : 'Put this personal thread in a shared inbox'} onPress={() => setMode('move')} colors={c} testId="own-move-btn" />}
              {can?.graduate && <ActionRow icon="call" label={`Move to ${isMine ? 'my' : firstName(owner?.name) + "'s"} direct line`} sub="Off the shared number for good" onPress={() => setMode('graduate')} colors={c} testId="own-graduate-btn" color="#34C759" />}
            </View>
          </View>
        )}

        {/* History */}
        {data.history.length > 0 && (
          <View>
            <Eyebrow colors={c}>HISTORY</Eyebrow>
            <View style={{ gap: 6 }}>
              {[...data.history].reverse().slice(0, 6).map((h, i) => (
                <View key={i} style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }} {...tid(`own-history-${i}`)}>
                  <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: GOLD, marginTop: 6 }} />
                  <Text style={{ flex: 1, fontSize: 13, color: c.textSecondary, lineHeight: 18 }}>{historyLine(h)}{h.note ? ` · "${h.note}"` : ''} · {timeAgo(h.at)}</Text>
                </View>
              ))}
            </View>
          </View>
        )}
      </View>
    );
  };

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={onClose} {...tid('ownership-sheet-backdrop')} />
        <View style={{ backgroundColor: c.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '90%' }} {...tid('ownership-sheet')}>
          <View style={{ alignItems: 'center', paddingTop: 8 }}><View style={{ width: 36, height: 4, borderRadius: 2, backgroundColor: c.border }} /></View>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 18, fontWeight: '800', color: c.text }}>Who's on this</Text>
              <Text style={{ fontSize: 12, color: c.textSecondary, marginTop: 2 }}>{loading ? 'Refreshing' : inbox ? `${inbox.name} · shared inbox` : 'Personal conversation'}</Text>
            </View>
            <TouchableOpacity onPress={onClose} hitSlop={8} {...tid('ownership-sheet-close')}>
              <Ionicons name="close" size={24} color={c.text} />
            </TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: Platform.OS === 'ios' ? 32 : 20 }} keyboardShouldPersistTaps="handled">
            {body()}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
