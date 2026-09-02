import React from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export type CallAttempt = { user_ids: string[]; delay_seconds: number };
type Rep = { _id: string; name?: string; email?: string; role?: string };

const MAX = 4;
const DELAYS = [30, 60, 90, 120, 180];

export const ContactModeToggle = ({ value, onChange, colors }: { value: 'text_only' | 'text_and_call'; onChange: (v: 'text_only' | 'text_and_call') => void; colors: any }) => (
  <View>
    <Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 8 }}>Customer Contact</Text>
    <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
      {([['text_only', 'chatbubble-outline', 'Text only'], ['text_and_call', 'call-outline', 'Text + Call']] as const).map(([v, icon, label]) => {
        const on = value === v;
        return (
          <TouchableOpacity
            key={v}
            onPress={() => onChange(v)}
            style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 9, backgroundColor: on ? colors.card : 'transparent', borderWidth: on ? 1 : 0, borderColor: '#C9A962' }}
            testID={`contact-mode-${v}`}
            dataSet={{ testid: `contact-mode-${v}` } as any}
          >
            <Ionicons name={icon as any} size={16} color={on ? '#C9A962' : colors.textSecondary} />
            <Text style={{ fontWeight: '700', color: on ? colors.text : colors.textSecondary, fontSize: 14 }}>{label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 6, lineHeight: 17 }}>
      {value === 'text_and_call'
        ? 'Intake text goes to the customer, then the system rings your reps. First to press 1 hears the lead details and is connected to the customer.'
        : 'Intake text goes to the customer and reps get a push notification. Nobody is called.'}
    </Text>
  </View>
);

export const LeadCallLadder = ({ attempts, reps, onChange, colors }: { attempts: CallAttempt[]; reps: Rep[]; onChange: (a: CallAttempt[]) => void; colors: any }) => {
  const update = (i: number, patch: Partial<CallAttempt>) => onChange(attempts.map((a, idx) => (idx === i ? { ...a, ...patch } : a)));
  const toggleRep = (i: number, uid: string) => {
    const cur = attempts[i].user_ids;
    update(i, { user_ids: cur.includes(uid) ? cur.filter(u => u !== uid) : [...cur, uid] });
  };
  const addAttempt = () => {
    if (attempts.length >= MAX) return;
    const prev = attempts[attempts.length - 1];
    onChange([...attempts, { user_ids: prev ? [...prev.user_ids] : [], delay_seconds: 60 }]);
  };
  const remove = (i: number) => onChange(attempts.filter((_, idx) => idx !== i));

  return (
    <View testID="lead-call-ladder" dataSet={{ testid: 'lead-call-ladder' } as any}>
      <Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 4 }}>Call Ladder (up to {MAX} attempts)</Text>
      <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 10, lineHeight: 17 }}>
        Each attempt rings everyone on it at once for about 25 seconds. Add a manager or another team on later attempts to escalate. Minimum delay between attempts is 30s. Dialing stops the moment someone claims.
      </Text>

      {attempts.map((a, i) => (
        <View key={i} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, marginBottom: 10, backgroundColor: colors.surface }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 8 }}>
            <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center', marginRight: 8 }}>
              <Text style={{ fontWeight: '800', color: '#000', fontSize: 13 }}>{i + 1}</Text>
            </View>
            <Text style={{ flex: 1, fontWeight: '700', color: colors.text }}>
              {i === 0 ? 'Rings immediately' : `Rings ${a.delay_seconds}s after attempt ${i}`}
            </Text>
            {attempts.length > 1 && (
              <TouchableOpacity onPress={() => remove(i)} hitSlop={8} testID={`ladder-remove-${i}`} dataSet={{ testid: `ladder-remove-${i}` } as any}>
                <Ionicons name="trash-outline" size={18} color="#FF3B30" />
              </TouchableOpacity>
            )}
          </View>

          {i > 0 && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginRight: 4 }}>Delay</Text>
              {DELAYS.map(d => (
                <TouchableOpacity key={d} onPress={() => update(i, { delay_seconds: d })} style={{ paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, backgroundColor: a.delay_seconds === d ? '#C9A962' : colors.card, borderWidth: 1, borderColor: a.delay_seconds === d ? '#C9A962' : colors.border }}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: a.delay_seconds === d ? '#000' : colors.text }}>{d}s</Text>
                </TouchableOpacity>
              ))}
              <TextInput
                value={String(a.delay_seconds)}
                onChangeText={v => update(i, { delay_seconds: Math.max(30, parseInt(v.replace(/\D/g, '') || '0', 10)) })}
                keyboardType="number-pad"
                style={{ width: 56, paddingVertical: 5, paddingHorizontal: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border, color: colors.text, backgroundColor: colors.card, fontSize: 12, textAlign: 'center' }}
                testID={`ladder-delay-${i}`}
                dataSet={{ testid: `ladder-delay-${i}` } as any}
              />
            </View>
          )}

          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {reps.map(r => {
              const on = a.user_ids.includes(r._id);
              return (
                <TouchableOpacity
                  key={r._id}
                  onPress={() => toggleRep(i, r._id)}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, backgroundColor: on ? '#34C75922' : colors.card, borderWidth: 1, borderColor: on ? '#34C759' : colors.border }}
                  testID={`ladder-${i}-rep-${r._id}`}
                  dataSet={{ testid: `ladder-${i}-rep-${r._id}` } as any}
                >
                  {on && <Ionicons name="checkmark" size={13} color="#34C759" />}
                  <Text style={{ fontSize: 13, color: colors.text, fontWeight: on ? '700' : '500' }}>{r.name || r.email}</Text>
                  {r.role && r.role !== 'user' && <Text style={{ fontSize: 10, color: colors.textSecondary }}>{r.role.replace('_', ' ')}</Text>}
                </TouchableOpacity>
              );
            })}
          </View>
          {a.user_ids.length === 0 && <Text style={{ fontSize: 12, color: '#FF9500', marginTop: 6 }}>Pick at least one rep or this attempt is skipped.</Text>}
        </View>
      ))}

      {attempts.length < MAX && (
        <TouchableOpacity onPress={addAttempt} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', borderColor: '#C9A962' }} testID="ladder-add-attempt" dataSet={{ testid: 'ladder-add-attempt' } as any}>
          <Ionicons name="add-circle-outline" size={18} color="#C9A962" />
          <Text style={{ color: '#C9A962', fontWeight: '700' }}>Add attempt {attempts.length + 1}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

export const WebsiteFormRouting = ({ isDefault, pages, allPages, routed, sourceId, onChange, colors }: {
  isDefault: boolean; pages: string[]; allPages: string[]; routed: Record<string, { id: string; name: string }>; sourceId: string;
  onChange: (patch: { website_default?: boolean; website_pages?: string[] }) => void; colors: any;
}) => {
  const pretty = (p: string) => p.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const defaultOwner = routed['__default__'];
  return (
    <View testID="website-form-routing" dataSet={{ testid: 'website-form-routing' } as any}>
      <Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 4 }}>Website "Book a Demo" Forms</Text>
      <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 10, lineHeight: 17 }}>
        Route marketing-site forms into this workflow. Every lead keeps its page, button, channel and UTM attribution.
      </Text>
      <TouchableOpacity
        onPress={() => onChange({ website_default: !isDefault })}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: isDefault ? '#C9A96222' : colors.surface, borderWidth: 1, borderColor: isDefault ? '#C9A962' : colors.border, marginBottom: 10 }}
        testID="website-default-toggle"
        dataSet={{ testid: 'website-default-toggle' } as any}
      >
        <Ionicons name={isDefault ? 'checkbox' : 'square-outline'} size={22} color={isDefault ? '#C9A962' : colors.textSecondary} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontWeight: '700', color: colors.text }}>Catch-all for every website form</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>
            {defaultOwner && defaultOwner.id !== sourceId ? `Currently: ${defaultOwner.name}. Turning this on moves it here.` : 'Pages without a specific route land here.'}
          </Text>
        </View>
      </TouchableOpacity>
      <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 6 }}>Or pick specific pages:</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {allPages.map(p => {
          const on = pages.includes(p);
          const other = routed[p] && routed[p].id !== sourceId ? routed[p].name : null;
          return (
            <TouchableOpacity
              key={p}
              onPress={() => onChange({ website_pages: on ? pages.filter(x => x !== p) : [...pages, p] })}
              style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, backgroundColor: on ? '#C9A962' : colors.card, borderWidth: 1, borderColor: on ? '#C9A962' : colors.border }}
              testID={`website-page-${p}`}
              dataSet={{ testid: `website-page-${p}` } as any}
            >
              <Text style={{ fontSize: 13, fontWeight: on ? '700' : '500', color: on ? '#000' : colors.text }}>
                {pretty(p)}{other ? ` (${other})` : ''}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
};
