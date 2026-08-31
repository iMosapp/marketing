/**
 * DateTimeField — cross-platform date + optional time picker.
 * Web: native <input type="date|time">. Native: @react-native-community/datetimepicker.
 */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import DateTimePicker from '@react-native-community/datetimepicker';

const pad = (n: number) => String(n).padStart(2, '0');
export const fmtDateLocal = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const fmtTimeLabel = (time: string) => {
  const [h, m] = time.split(':').map(Number);
  const hh = h % 12 || 12;
  return `${hh}:${pad(m)} ${h >= 12 ? 'PM' : 'AM'}`;
};

export function DateTimeField({ colors, date, setDate, time, setTime, accent = '#C9A962' }: any) {
  const [showDate, setShowDate] = useState(false);
  const [showTime, setShowTime] = useState(false);

  if (Platform.OS === 'web') {
    const inputStyle: any = {
      padding: 12, borderRadius: 10, backgroundColor: colors.card, color: colors.text,
      border: `1.5px solid ${colors.border}`, fontSize: 15, boxSizing: 'border-box',
    };
    return (
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {React.createElement('input', {
          type: 'date',
          value: fmtDateLocal(date),
          onChange: (e: any) => {
            if (!e.target.value) return;
            const [y, m, d] = e.target.value.split('-').map(Number);
            const nd = new Date(date); nd.setFullYear(y, m - 1, d); setDate(nd);
          },
          style: { ...inputStyle, flex: 1 },
          'data-testid': 'dtf-date-input',
        })}
        {React.createElement('input', {
          type: 'time',
          value: time || '',
          onChange: (e: any) => setTime(e.target.value || null),
          style: { ...inputStyle, width: 130 },
          'data-testid': 'dtf-time-input',
        })}
      </View>
    );
  }

  const timeAsDate = () => {
    const d = new Date(date);
    if (time) { const [h, m] = time.split(':').map(Number); d.setHours(h, m, 0, 0); }
    else d.setHours(9, 0, 0, 0);
    return d;
  };

  const btn = {
    flexDirection: 'row' as const, alignItems: 'center' as const, justifyContent: 'space-between' as const,
    backgroundColor: colors.card, borderRadius: 10, borderWidth: 1.5, borderColor: colors.border,
    paddingHorizontal: 12, paddingVertical: 12,
  };

  return (
    <View>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TouchableOpacity style={[btn, { flex: 1 }]} onPress={() => { setShowDate(v => !v); setShowTime(false); }} testID="dtf-date-btn" dataSet={{ testid: 'dtf-date-btn' } as any}>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, color: colors.text }}>
            {date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
          </Text>
          <Ionicons name="calendar-outline" size={17} color={accent} />
        </TouchableOpacity>
        <TouchableOpacity style={[btn, { width: 130 }]} onPress={() => { setShowTime(v => !v); setShowDate(false); }} testID="dtf-time-btn" dataSet={{ testid: 'dtf-time-btn' } as any}>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, color: time ? colors.text : colors.textTertiary }}>
            {time ? fmtTimeLabel(time) : 'Add time'}
          </Text>
          <Ionicons name="time-outline" size={17} color={accent} />
        </TouchableOpacity>
      </View>
      {showDate && (
        <DateTimePicker
          value={date}
          mode="date"
          display={Platform.OS === 'ios' ? 'spinner' : 'default'}
          onChange={(_: any, d?: Date) => { if (Platform.OS !== 'ios') setShowDate(false); if (d) setDate(d); }}
          themeVariant="dark"
          style={{ height: 130, alignSelf: 'center' }}
        />
      )}
      {showTime && (
        <DateTimePicker
          value={timeAsDate()}
          mode="time"
          display={Platform.OS === 'ios' ? 'spinner' : 'default'}
          onChange={(_: any, d?: Date) => {
            if (Platform.OS !== 'ios') setShowTime(false);
            if (d) setTime(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
          }}
          themeVariant="dark"
          style={{ height: 130, alignSelf: 'center' }}
        />
      )}
      {time ? (
        <TouchableOpacity onPress={() => setTime(null)} style={{ alignSelf: 'flex-end', marginTop: 6 }} testID="dtf-clear-time" dataSet={{ testid: 'dtf-clear-time' } as any}>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, color: colors.textTertiary }}>Clear time</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

export const APPT_TYPES = [
  { key: 'call', label: 'Call', icon: 'call' },
  { key: 'appointment', label: 'Appointment', icon: 'calendar' },
  { key: 'delivery', label: 'Delivery', icon: 'cube' },
  { key: 'meeting', label: 'Meeting', icon: 'people' },
] as const;

export function ApptTypeRow({ colors, value, onChange, accent = '#C9A962' }: any) {
  return (
    <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
      {APPT_TYPES.map(t => {
        const active = value === t.key;
        return (
          <TouchableOpacity
            key={t.key}
            onPress={() => onChange(active ? null : t.key)}
            style={{
              flexDirection: 'row', alignItems: 'center', gap: 5,
              paddingHorizontal: 12, paddingVertical: 8, borderRadius: 18, borderWidth: 1.5,
              borderColor: active ? accent : colors.border,
              backgroundColor: active ? `${accent}20` : colors.card,
            }}
            testID={`appt-type-${t.key}`}
            dataSet={{ testid: `appt-type-${t.key}` } as any}
          >
            <Ionicons name={t.icon as any} size={14} color={active ? accent : colors.textSecondary} />
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13.5, fontWeight: '600', color: active ? accent : colors.text }}>{t.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}
