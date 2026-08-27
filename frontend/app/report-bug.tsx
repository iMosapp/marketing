import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, ScrollView, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';

const CATEGORIES = [
  { key: 'bug', label: 'Bug', icon: 'bug-outline', color: '#FF3B30' },
  { key: 'suggestion', label: 'Suggestion', icon: 'bulb-outline', color: '#FF9500' },
  { key: 'other', label: 'Other', icon: 'chatbox-ellipses-outline', color: '#007AFF' },
];

export default function ReportBugScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const [category, setCategory] = useState('bug');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async () => {
    if (!user?._id || !description.trim()) return;
    setSubmitting(true);
    try {
      await api.post(`/bug-reports/${user._id}`, {
        category,
        description: description.trim(),
        platform: `${Platform.OS} ${Platform.Version || ''}`.trim(),
      });
      setDone(true);
    } catch {
      showSimpleAlert('Error', 'Could not submit your report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top', 'bottom']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }}>
          <View style={{ width: 100, height: 100, borderRadius: 50, backgroundColor: '#34C75920', alignItems: 'center', justifyContent: 'center', marginBottom: 24 }}>
            <Ionicons name="checkmark" size={52} color="#34C759" />
          </View>
          <Text style={{ fontSize: 24, fontWeight: '800', color: colors.text, marginBottom: 8 }}>Report Sent!</Text>
          <Text style={{ fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 22 }}>
            Thanks for helping make the app better. The team has been notified and will take a look.
          </Text>
          <TouchableOpacity
            style={{ backgroundColor: '#C9A962', borderRadius: 14, paddingVertical: 16, paddingHorizontal: 48, marginTop: 32 }}
            onPress={() => router.back()}
            data-testid="report-bug-done-btn"
          >
            <Text style={{ fontSize: 17, fontWeight: '700', color: '#000' }}>Done</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top', 'bottom']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.surface }}>
        <TouchableOpacity onPress={() => router.back()} data-testid="report-bug-back-btn">
          <Ionicons name="close" size={28} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }} numberOfLines={1}>Report a Bug</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView contentContainerStyle={{ padding: 24, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
        <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 1, marginBottom: 10 }}>WHAT KIND OF FEEDBACK?</Text>
        <View style={{ flexDirection: 'row', gap: 10, marginBottom: 24 }}>
          {CATEGORIES.map(c => {
            const active = category === c.key;
            return (
              <TouchableOpacity
                key={c.key}
                style={{
                  flex: 1, alignItems: 'center', paddingVertical: 14, borderRadius: 12,
                  backgroundColor: active ? `${c.color}18` : colors.card,
                  borderWidth: 1.5, borderColor: active ? c.color : colors.surface,
                }}
                onPress={() => setCategory(c.key)}
                data-testid={`report-category-${c.key}`}
              >
                <Ionicons name={c.icon as any} size={22} color={active ? c.color : colors.textSecondary} />
                <Text style={{ fontSize: 13, fontWeight: '600', marginTop: 6, color: active ? c.color : colors.textSecondary }} numberOfLines={1}>{c.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 1, marginBottom: 10 }}>WHAT HAPPENED?</Text>
        <TextInput
          style={{
            backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 16, color: colors.text,
            borderWidth: 1.5, borderColor: colors.surface, height: 160, textAlignVertical: 'top',
          }}
          placeholder="Describe the issue — what were you doing, what did you expect, and what happened instead?"
          placeholderTextColor={colors.textSecondary}
          value={description}
          onChangeText={setDescription}
          multiline
          data-testid="report-description-input"
        />

        <TouchableOpacity
          style={{
            flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
            backgroundColor: '#C9A962', borderRadius: 14, paddingVertical: 18, marginTop: 24,
            opacity: description.trim() && !submitting ? 1 : 0.5,
          }}
          onPress={handleSubmit}
          disabled={!description.trim() || submitting}
          data-testid="report-submit-btn"
        >
          {submitting ? (
            <ActivityIndicator size="small" color="#000" />
          ) : (
            <>
              <Ionicons name="paper-plane" size={20} color="#000" />
              <Text style={{ fontSize: 17, fontWeight: '700', color: '#000' }}>Send Report</Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}
