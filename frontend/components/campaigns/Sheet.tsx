import React from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, KeyboardAvoidingView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from './utils';

type ShellProps = {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  testId: string;
  colors: any;
};

// Bottom sheet used by every campaign editor sub-screen (same look as the Workflows edit sheet).
export function SheetShell({ title, subtitle, onClose, children, footer, testId, colors }: ShellProps) {
  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={onClose} {...tid(`${testId}-backdrop`)} />
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%' }} {...tid(testId)}>
            <View style={{ alignItems: 'center', paddingTop: 8 }}>
              <View style={{ width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border }} />
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{title}</Text>
                {subtitle ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{subtitle}</Text> : null}
              </View>
              <TouchableOpacity onPress={onClose} hitSlop={8} {...tid(`${testId}-close`)}>
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 16, gap: 16 }} keyboardShouldPersistTaps="handled">
              {children}
            </ScrollView>
            {footer ? <View style={{ paddingHorizontal: 16, paddingBottom: Platform.OS === 'ios' ? 28 : 16, paddingTop: 8, gap: 8 }}>{footer}</View> : null}
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

export const Eyebrow = ({ children, colors, style }: { children: React.ReactNode; colors: any; style?: any }) => (
  <Text style={[{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }, style]}>{children}</Text>
);

export const OptionRow = ({ label, sub, selected, onPress, testId, colors }: { label: string; sub?: string; selected: boolean; onPress: () => void; testId: string; colors: any }) => (
  <TouchableOpacity onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, backgroundColor: selected ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: selected ? GOLD : 'transparent' }} {...tid(testId)}>
    <Ionicons name={selected ? 'radio-button-on' : 'radio-button-off'} size={18} color={selected ? GOLD : colors.textSecondary} />
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{label}</Text>
      {sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>{sub}</Text> : null}
    </View>
  </TouchableOpacity>
);

export const Chip = ({ label, active, onPress, testId, colors, icon, color }: { label: string; active?: boolean; onPress?: () => void; testId: string; colors: any; icon?: any; color?: string }) => {
  const c = color || GOLD;
  return (
    <TouchableOpacity onPress={onPress} disabled={!onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: active ? c : colors.card, borderWidth: 1, borderColor: active ? c : colors.border }} {...tid(testId)}>
      {icon ? <Ionicons name={icon} size={13} color={active ? '#111' : c} /> : null}
      <Text style={{ fontSize: 13, fontWeight: active ? '800' : '600', color: active ? '#111' : colors.text }}>{label}</Text>
    </TouchableOpacity>
  );
};

export const GoldButton = ({ label, onPress, disabled, testId, icon }: { label: string; onPress: () => void; disabled?: boolean; testId: string; icon?: any }) => (
  <TouchableOpacity onPress={onPress} disabled={disabled} style={{ height: 50, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: disabled ? 0.5 : 1 }} {...tid(testId)}>
    {icon ? <Ionicons name={icon} size={18} color="#111" /> : null}
    <Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>{label}</Text>
  </TouchableOpacity>
);

export const Segmented = ({ options, value, onChange, colors, testId }: { options: { value: string; label: string; icon?: any }[]; value: string; onChange: (v: string) => void; colors: any; testId: string }) => (
  <View style={{ flexDirection: 'row', backgroundColor: colors.card, borderRadius: 14, padding: 4, gap: 4 }}>
    {options.map(o => {
      const on = o.value === value;
      return (
        <TouchableOpacity key={o.value} onPress={() => onChange(o.value)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 11, backgroundColor: on ? GOLD : 'transparent' }} {...tid(`${testId}-${o.value}`)}>
          {o.icon ? <Ionicons name={o.icon} size={15} color={on ? '#111' : colors.textSecondary} /> : null}
          <Text style={{ fontSize: 14, fontWeight: '800', color: on ? '#111' : colors.textSecondary }}>{o.label}</Text>
        </TouchableOpacity>
      );
    })}
  </View>
);
