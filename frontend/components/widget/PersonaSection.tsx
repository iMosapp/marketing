import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Image, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';
import { Section, Label, Hint } from '../inbox/InboxEditorParts';
import { Chips, Field, ToggleRow } from './parts';
import { ImageField } from './ImageField';

type Member = { id: string; name: string; first: string; title: string; photo: string };
type Props = { persona: any; setPersona: (p: any) => void; widgetId: string; colors: any; showToast: (m: string, t?: any, d?: number) => void; canManage: boolean };

// Who the website assistant is: a real team member's face and name, or a custom VA. Off = "Jessi".
export const PersonaSection = ({ persona, setPersona, widgetId, colors, showToast, canManage }: Props) => {
  const p = persona || {};
  const [team, setTeam] = useState<Member[]>([]);
  useEffect(() => {
    if (!p.on || p.source !== 'team') return;
    api.get(`/widgets/${widgetId}/team`).then(r => setTeam(r.data.members || [])).catch(() => setTeam([]));
  }, [widgetId, p.on, p.source]);

  return (
    <Section colors={colors} testId="widget-section-persona">
      <ToggleRow label="Give the assistant a name and a face" hint="Visitors chat with a named assistant trained on your Facts, Scripted answers and website instead of a generic 'Jessi'. Reps who jump in still show as themselves." value={!!p.on} onChange={v => setPersona({ on: v })} colors={colors} testId="widget-persona-on" />
      {p.on ? (
        <>
          <Label colors={colors} top>Who is it?</Label>
          <Chips options={[{ value: 'team', label: 'A team member', icon: 'people-outline' }, { value: 'custom', label: 'A custom assistant', icon: 'sparkles-outline' }]} value={p.source || 'custom'} onChange={v => setPersona({ source: v })} colors={colors} testId="widget-persona-source" />
          {p.source === 'team' ? (
            <>
              <Hint colors={colors}>Their profile photo, first name and title are used live, so a new headshot in the app updates the website too.</Hint>
              {team.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('widget-persona-team-empty')}>No one at this store yet, or still loading.</Text> : (
                <ScrollView horizontal showsVerticalScrollIndicator={false} showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingVertical: 4 }} {...tid('widget-persona-team')}>
                  {team.map(m => {
                    const on = p.user_id === m.id;
                    return (
                      <TouchableOpacity key={m.id} onPress={() => setPersona({ user_id: m.id })} style={{ width: 86, alignItems: 'center', gap: 6, padding: 8, borderRadius: 14, borderWidth: 2, borderColor: on ? GOLD : colors.border, backgroundColor: on ? `${GOLD}22` : colors.surface }} {...tid(`widget-persona-member-${m.id}`)}>
                        <View style={{ width: 52, height: 52, borderRadius: 26, overflow: 'hidden', backgroundColor: colors.border, alignItems: 'center', justifyContent: 'center' }}>
                          {m.photo ? <Image source={{ uri: m.photo }} style={{ width: 52, height: 52 }} /> : <Ionicons name="person" size={24} color={colors.textSecondary} />}
                        </View>
                        <Text style={{ fontSize: 12, fontWeight: '800', color: colors.text }} numberOfLines={1}>{m.first}</Text>
                        {m.title ? <Text style={{ fontSize: 10, color: colors.textSecondary, textAlign: 'center' }} numberOfLines={2}>{m.title}</Text> : null}
                        {!m.photo ? <Text style={{ fontSize: 9, color: '#FF9500' }}>no photo</Text> : null}
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              )}
              <Field label="Title on the website (optional override)" value={p.title || ''} onChange={v => setPersona({ title: v })} placeholder="Product Specialist" colors={colors} testId="widget-persona-title" maxLength={60} />
            </>
          ) : (
            <>
              <Field label="Name" value={p.name || ''} onChange={v => setPersona({ name: v })} placeholder="Amanda" colors={colors} testId="widget-persona-name" maxLength={40} />
              <Field label="Title" value={p.title || ''} onChange={v => setPersona({ title: v })} placeholder="Product Specialist" colors={colors} testId="widget-persona-title" maxLength={60} />
              <ImageField label="Photo" hint="A friendly headshot, square, well lit. This is the face visitors see in the corner of your site." value={p.photo_url || ''} onChange={v => setPersona({ photo_url: v })} widgetId={widgetId} target="avatar" colors={colors} testId="widget-persona-photo" round showToast={showToast} canManage={canManage} />
            </>
          )}
          <Field label="Personality" hint="How they talk. A few words is plenty." value={p.tone || ''} onChange={v => setPersona({ tone: v })} placeholder="Warm, quick, a little playful" colors={colors} testId="widget-persona-tone" maxLength={160} />
          <Field label="One line about them (optional)" value={p.intro || ''} onChange={v => setPersona({ intro: v })} placeholder="Twelve years helping families pick the right truck." colors={colors} testId="widget-persona-intro" maxLength={240} />
          <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 10 }}>
            <Ionicons name="shield-checkmark-outline" size={16} color={colors.textSecondary} />
            <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>A small "AI assistant" tag sits next to the name in the chat header. Bot-disclosure laws in several states require it; the launcher and teaser stay fully human-looking.</Text>
          </View>
        </>
      ) : null}
    </Section>
  );
};
