import React from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Chip, Label, DEPTS, LIGHT, GOLD, RED, tid } from './shared';

export type KPerson = { key: string; id?: string; name: string; phone: string; department: string; title: string };
type Props = { people: KPerson[]; onChange: (p: KPerson[]) => void };

const inp = { backgroundColor: LIGHT.surface, borderRadius: 10, borderWidth: 1, borderColor: LIGHT.border, paddingHorizontal: 10, height: 42, color: LIGHT.text, fontSize: 15 } as const;
export const newPerson = (department = 'sales'): KPerson => ({ key: Math.random().toString(36).slice(2), name: '', phone: '', department, title: '' });

// The people we shop: one row each. Existing ones arrive prefilled (with id); blank rows are ignored on save.
export const KickoffPeople = ({ people, onChange }: Props) => {
  const set = (key: string, patch: Partial<KPerson>) => onChange(people.map(p => (p.key === key ? { ...p, ...patch } : p)));
  const remove = (key: string) => onChange(people.filter(p => p.key !== key));
  return (
    <View style={{ gap: 12 }}>
      {DEPTS.map(d => {
        const rows = people.filter(p => p.department === d.key);
        return (
          <View key={d.key} style={{ gap: 8 }}>
            <Label t={`${d.label.toUpperCase()} · ${rows.length}`} colors={LIGHT} />
            {rows.map(p => (
              <View key={p.key} style={{ backgroundColor: LIGHT.card, borderRadius: 14, borderWidth: 1, borderColor: LIGHT.border, padding: 10, gap: 8 }} {...tid(`kickoff-person-${p.key}`)}>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TextInput value={p.name} onChangeText={v => set(p.key, { name: v })} placeholder="Full name" placeholderTextColor={LIGHT.textSecondary} style={[inp, { flex: 1.3 }]} {...tid(`kickoff-person-name-${p.key}`)} />
                  <TextInput value={p.phone} onChangeText={v => set(p.key, { phone: v })} placeholder="Cell number" placeholderTextColor={LIGHT.textSecondary} keyboardType="phone-pad" style={[inp, { flex: 1 }]} {...tid(`kickoff-person-phone-${p.key}`)} />
                </View>
                <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                  <TextInput value={p.title} onChangeText={v => set(p.key, { title: v })} placeholder={d.key === 'service' ? 'Title (Service advisor)' : 'Title (Sales consultant)'} placeholderTextColor={LIGHT.textSecondary} style={[inp, { flex: 1 }]} {...tid(`kickoff-person-title-${p.key}`)} />
                  <Chip label={d.key === 'sales' ? 'Move to Service' : 'Move to Sales'} small active={false} onPress={() => set(p.key, { department: d.key === 'sales' ? 'service' : 'sales' })} colors={LIGHT} testID={`kickoff-person-dept-${p.key}`} />
                  <TouchableOpacity onPress={() => remove(p.key)} hitSlop={8} {...tid(`kickoff-person-remove-${p.key}`)}><Ionicons name="trash-outline" size={20} color={RED} /></TouchableOpacity>
                </View>
              </View>
            ))}
            <TouchableOpacity onPress={() => onChange([...people, newPerson(d.key)])} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, height: 42, borderRadius: 12, borderWidth: 1, borderColor: GOLD, justifyContent: 'center' }} {...tid(`kickoff-add-${d.key}`)}>
              <Ionicons name="person-add" size={16} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>Add a {d.label.toLowerCase()} person</Text>
            </TouchableOpacity>
          </View>
        );
      })}
    </View>
  );
};
