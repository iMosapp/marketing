import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, ScrollView, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useThemeStore } from '../store/themeStore';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';

type Category = { key: string; label: string; icon: string; color: string; placeholder: string };

const BUG_CATEGORIES: Category[] = [
  { key: 'bug', label: 'Bug', icon: 'bug-outline', color: '#FF3B30', placeholder: 'Describe the issue: what were you doing, what did you expect, and what happened instead?' },
  { key: 'suggestion', label: 'Suggestion', icon: 'bulb-outline', color: '#FF9500', placeholder: 'What would make the app better for you?' },
  { key: 'other', label: 'Other', icon: 'chatbox-ellipses-outline', color: '#5AC8FA', placeholder: 'Tell us anything.' },
];

// Stage 3: pilot customers send feedback in their own words. Same pipeline (founder email + push), friendlier doors.
const PILOT_CATEGORIES: Category[] = [
  { key: 'question', label: 'Question', icon: 'help-circle-outline', color: '#007AFF', placeholder: 'What are you trying to do? Ask in your own words and we will answer by text or email.' },
  { key: 'problem', label: 'Problem', icon: 'alert-circle-outline', color: '#FF3B30', placeholder: 'What happened, and what did you expect? Mention the screen if you can.' },
  { key: 'suggestion', label: 'Suggestion', icon: 'bulb-outline', color: '#FF9500', placeholder: 'What would make this easier or more useful for you?' },
];

export default function ReportBugScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const { from } = useLocalSearchParams<{ from?: string }>();
  const pilot = !!user?.pilot;
  const categories = pilot ? PILOT_CATEGORIES : BUG_CATEGORIES;
  const title = pilot ? 'Send Feedback' : 'Report a Bug';
  const [category, setCategory] = useState(categories[0].key);
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const current = categories.find(c => c.key === category) || categories[0];

  const handleSubmit = async () => {
    if (!user?._id || !description.trim()) return;
    setSubmitting(true);
    try {
      await api.post(`/bug-reports/${user._id}`, {
        category,
        description: description.trim(),
        platform: `${Platform.OS} ${Platform.Version || ''}`.trim(),
        screen: from || '',
      });
      setDone(true);
    } catch {
      showSimpleAlert('Error', 'Could not send that. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top', 'bottom']}>
        <ScreenHeader title={title} testID="report-bug-header" />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }} data-testid="report-bug-success">
          <View style={{ width: 100, height: 100, borderRadius: 50, backgroundColor: '#34C75920', alignItems: 'center', justifyContent: 'center', marginBottom: 24 }}>
            <Ionicons name="checkmark" size={52} color="#34C759" />
          </View>
          <Text style={{ fontSize: 24, fontWeight: '800', color: colors.text, marginBottom: 8 }}>{pilot ? 'Got it. Thank you!' : 'Report Sent!'}</Text>
          <Text style={{ fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 22 }}>
            {pilot
              ? 'Your message went straight to the founder. Expect a reply by text or email, usually the same day.'
              : 'Thanks for helping make the app better. The team has been notified and will take a look.'}
          </Text>
          <TouchableOpacity
            style={{ backgroundColor: '#C9A962', borderRadius: 14, paddingVertical: 16, paddingHorizontal: 48, marginTop: 32 }}
            onPress={() => (router.canGoBack() ? router.back() : router.replace((pilot ? '/(tabs)/home' : '/(tabs)/more') as any))}
            testID="report-bug-done-btn" dataSet={{ testid: 'report-bug-done-btn' } as any}
          >
            <Text style={{ fontSize: 17, fontWeight: '700', color: '#000' }}>Done</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top', 'bottom']}>
      <ScreenHeader title={title} testID="report-bug-header" />

      <ScrollView contentContainerStyle={{ padding: 24, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
        <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 10 }}>{pilot ? 'WHAT IS IT?' : 'WHAT KIND OF FEEDBACK?'}</Text>
        <View style={{ flexDirection: 'row', gap: 10, marginBottom: 24 }}>
          {categories.map(c => {
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

        <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 1, marginBottom: 10 }}>{pilot ? 'TELL US' : 'WHAT HAPPENED?'}</Text>
        <TextInput
          style={{
            backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 16, color: colors.text,
            borderWidth: 1.5, borderColor: colors.surface, height: 160, textAlignVertical: 'top',
          }}
          placeholder={current.placeholder}
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
              <Text style={{ fontSize: 17, fontWeight: '700', color: '#000' }}>{pilot ? 'Send' : 'Send Report'}</Text>
            </>
          )}
        </TouchableOpacity>
        {pilot ? (
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, textAlign: 'center', marginTop: 14, lineHeight: 18 }}>
            Goes to the founder with your name and company, so no need to introduce yourself.
          </Text>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
