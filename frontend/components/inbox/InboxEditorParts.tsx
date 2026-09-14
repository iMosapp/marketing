import React from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Avatar } from '../Avatar';
import { GOLD, tid, RepCard } from './ownership';

export const INBOX_COLORS = ['#C9A962', '#34C759', '#5AC8FA', '#FF9500', '#AF52DE', '#FF2D55', '#FFD60A', '#8E8E93'];
export const ROUTING_OPTIONS = [
  { value: 'jump_ball', label: 'First to claim', sub: 'Everyone on the inbox gets pinged. Whoever replies or taps Claim first owns it.' },
  { value: 'round_robin', label: 'Take turns', sub: 'Each new customer goes to the next rep on shift. Nobody else is pinged.' },
  { value: 'weighted_round_robin', label: 'Weighted turns', sub: 'Like taking turns, but reps with a higher weight get more of the new customers.' },
];
export const AI_MODE_OPTIONS = [
  { value: 'auto_reply', label: 'Jessi answers until someone claims', sub: 'Keeps the customer warm and gathers details, then hands off.' },
  { value: 'auto_with_approval', label: 'Jessi answers, then holds for approval', sub: 'A few replies on her own, then drafts wait for a rep.' },
  { value: 'draft_only', label: 'Jessi drafts only', sub: 'Nothing goes out until a rep taps send.' },
  { value: 'off', label: 'Humans only', sub: 'No AI on this number. Reps get the ping and reply themselves.' },
];
export const AFTER_CLOSE_OPTIONS = [
  { value: 'move_to_rep', label: "Move to the rep's own line", sub: 'The customer gets a short bridge text from the rep and every future text lands with them.' },
  { value: 'stay', label: 'Stay on the shared number', sub: 'The thread keeps living in this inbox forever.' },
];
export const routingLabel = (v: string) => ROUTING_OPTIONS.find(o => o.value === v)?.label || 'First to claim';
export const aiModeLabel = (v: string) => AI_MODE_OPTIONS.find(o => o.value === v)?.label || 'Jessi answers until someone claims';

export const Section = ({ children, colors, testId }: { children: React.ReactNode; colors: any; testId?: string }) => (
  <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 4 }} {...(testId ? tid(testId) : {})}>{children}</View>
);
export const Label = ({ children, colors, top }: { children: React.ReactNode; colors: any; top?: boolean }) => (
  <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text, marginBottom: 6, marginTop: top ? 12 : 0 }}>{children}</Text>
);
export const Hint = ({ children, colors }: { children: React.ReactNode; colors: any }) => (
  <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 8, lineHeight: 17 }}>{children}</Text>
);
export const inputStyle = (colors: any) => ({ backgroundColor: colors.surface, borderRadius: 12, padding: 12, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border } as const);

export const OptionRows = ({ options, value, onChange, colors, testId }: { options: { value: string; label: string; sub?: string }[]; value: string; onChange: (v: string) => void; colors: any; testId: string }) => (
  <View style={{ gap: 6 }}>
    {options.map(o => {
      const on = value === o.value;
      return (
        <TouchableOpacity key={o.value} onPress={() => onChange(o.value)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: on ? GOLD : 'transparent' }} {...tid(`${testId}-${o.value}`)}>
          <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={18} color={on ? GOLD : colors.textSecondary} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{o.label}</Text>
            {o.sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>{o.sub}</Text> : null}
          </View>
        </TouchableOpacity>
      );
    })}
  </View>
);

export const ColorPicker = ({ value, onChange }: { value: string; onChange: (c: string) => void }) => (
  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
    {INBOX_COLORS.map(c => (
      <TouchableOpacity key={c} onPress={() => onChange(c)} style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: c, alignItems: 'center', justifyContent: 'center', borderWidth: value === c ? 3 : 0, borderColor: '#fff' }} {...tid(`inbox-color-${c.replace('#', '')}`)}>
        {value === c ? <Ionicons name="checkmark" size={14} color="#111" /> : null}
      </TouchableOpacity>
    ))}
  </View>
);

export const MergeChips = ({ tokens, onInsert, colors }: { tokens: string[]; onInsert: (t: string) => void; colors: any }) => (
  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
    {tokens.map(t => (
      <TouchableOpacity key={t} onPress={() => onInsert(t)} style={{ backgroundColor: colors.surface, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1, borderColor: colors.border }} {...tid(`merge-${t.replace(/[{}]/g, '')}`)}>
        <Text style={{ fontSize: 11, fontWeight: '700', color: GOLD, fontFamily: 'monospace' }}>{t}</Text>
      </TouchableOpacity>
    ))}
  </View>
);

type MemberProps = { options: RepCard[]; selected: string[]; weights: Record<string, number>; weighted: boolean; onToggle: (id: string) => void; onWeight: (id: string, w: number) => void; colors: any; storeName?: string | null; onSelectMany?: (ids: string[]) => void };

const MemberRow = ({ u, on, w, weighted, onToggle, onWeight, colors }: { u: RepCard; on: boolean; w: number; weighted: boolean; onToggle: (id: string) => void; onWeight: (id: string, w: number) => void; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 12, backgroundColor: on ? GOLD + '18' : colors.surface, borderWidth: 1, borderColor: on ? GOLD + '66' : 'transparent' }}>
    <TouchableOpacity onPress={() => onToggle(u.id)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`inbox-member-${u.id}`)}>
      <Ionicons name={on ? 'checkbox' : 'square-outline'} size={20} color={on ? GOLD : colors.textSecondary} />
      <Avatar photo={u.photo || null} name={u.name} size="sm" />
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{u.name}</Text>
        <Text style={{ fontSize: 11, color: u.has_number ? colors.textSecondary : '#FF9500' }}>{u.title || String(u.role || '').replace('_', ' ')}{u.has_number ? '' : ' · no personal number yet'}{u.on_team === false ? ' · not on this store yet' : ''}</Text>
      </View>
    </TouchableOpacity>
    {on && weighted && (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <TouchableOpacity onPress={() => onWeight(u.id, Math.max(1, w - 1))} hitSlop={6} {...tid(`inbox-weight-minus-${u.id}`)}><Ionicons name="remove-circle-outline" size={22} color={colors.textSecondary} /></TouchableOpacity>
        <Text style={{ fontSize: 14, fontWeight: '800', color: GOLD, minWidth: 16, textAlign: 'center' }} {...tid(`inbox-weight-${u.id}`)}>{w}</Text>
        <TouchableOpacity onPress={() => onWeight(u.id, Math.min(5, w + 1))} hitSlop={6} {...tid(`inbox-weight-plus-${u.id}`)}><Ionicons name="add-circle-outline" size={22} color={GOLD} /></TouchableOpacity>
      </View>
    )}
  </View>
);

// Multi-select of teammates: the store's team first (one tap adds them all), everyone else behind a search so a
// super admin can still pull in someone who is not linked to the store yet.
export const MemberPicker = ({ options, selected, weights, weighted, onToggle, onWeight, colors, storeName, onSelectMany }: MemberProps) => {
  const [showOthers, setShowOthers] = React.useState(false);
  const [q, setQ] = React.useState('');
  const team = options.filter(o => o.on_team !== false);
  const others = options.filter(o => o.on_team === false);
  const pickedOthers = others.filter(o => selected.includes(o.id));
  const allTeamOn = team.length > 0 && team.every(t => selected.includes(t.id));
  const visibleOthers = others.filter(o => !q.trim() || o.name.toLowerCase().includes(q.trim().toLowerCase()));
  const row = (u: RepCard) => <MemberRow key={u.id} u={u} on={selected.includes(u.id)} w={Number(weights[u.id] || 1)} weighted={weighted} onToggle={onToggle} onWeight={onWeight} colors={colors} />;
  return (
    <View style={{ gap: 6 }}>
      {options.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }}>No teammates found for this store yet.</Text>}
      {team.length > 0 && (
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{(storeName ? `ON ${storeName}` : 'YOUR TEAM').toUpperCase()} · {team.length}</Text>
          {onSelectMany && (
            <TouchableOpacity onPress={() => onSelectMany(allTeamOn ? [] : team.map(t => t.id))} hitSlop={8} {...tid('inbox-members-select-all')}>
              <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{allTeamOn ? 'Clear all' : 'Everyone on the team'}</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
      {team.map(row)}
      {pickedOthers.map(row)}
      {others.length > pickedOthers.length && (
        <View style={{ gap: 6, marginTop: 4 }}>
          <TouchableOpacity onPress={() => setShowOthers(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8 }} {...tid('inbox-members-show-others')}>
            <Ionicons name={showOthers ? 'chevron-down' : 'chevron-forward'} size={16} color={colors.textSecondary} />
            <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{showOthers ? 'Hide' : 'Add someone from outside this store'} · {others.length - pickedOthers.length}</Text>
          </TouchableOpacity>
          {showOthers && (
            <>
              <TextInput value={q} onChangeText={setQ} placeholder="Search by name" placeholderTextColor={colors.textSecondary} style={inputStyle(colors)} {...tid('inbox-members-search')} />
              <Text style={{ fontSize: 11, color: colors.textSecondary, lineHeight: 15 }}>Adding someone here also puts them on {storeName || 'this store'}'s team, so they show up in lead flows and reports.</Text>
              {visibleOthers.filter(o => !selected.includes(o.id)).slice(0, 40).map(row)}
              {visibleOthers.length > 40 && !q.trim() && <Text style={{ fontSize: 11, color: colors.textSecondary }}>Type a name to narrow it down.</Text>}
            </>
          )}
        </View>
      )}
    </View>
  );
};

type NumberProps = { value: string; numbers: { phone_number: string; friendly_name: string; available: boolean; current: boolean; taken_by?: string }[]; onChange: (v: string) => void; colors: any; fmt: (p: string) => string };

// Twilio numbers on the account (available / taken) plus a manual field.
export const NumberPicker = ({ value, numbers, onChange, colors, fmt }: NumberProps) => (
  <View style={{ gap: 8 }}>
    <TextInput value={value} onChangeText={onChange} placeholder="+1 (555) 555-0100" placeholderTextColor={colors.textSecondary} keyboardType="phone-pad" style={inputStyle(colors)} {...tid('inbox-phone-input')} />
    {numbers.length > 0 && (
      <View style={{ gap: 6 }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginTop: 4 }}>YOUR TWILIO NUMBERS</Text>
        {numbers.map(n => {
          const on = value.replace(/\D/g, '').endsWith(n.phone_number.replace(/\D/g, '').slice(-10)) && value.length > 0;
          const disabled = !n.available && !n.current;
          return (
            <TouchableOpacity key={n.phone_number} disabled={disabled} onPress={() => onChange(n.phone_number)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: on ? GOLD : 'transparent', opacity: disabled ? 0.5 : 1 }} {...tid(`inbox-number-${n.phone_number.replace(/\D/g, '')}`)}>
              <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={18} color={on ? GOLD : colors.textSecondary} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{fmt(n.phone_number)}</Text>
                <Text style={{ fontSize: 11, color: disabled ? '#FF9500' : colors.textSecondary }}>{n.current ? 'This inbox' : n.available ? (n.friendly_name !== n.phone_number ? n.friendly_name : 'Available') : n.taken_by || 'In use'}</Text>
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    )}
  </View>
);
