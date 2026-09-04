import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { resolveUserPhotoUrl } from '../../utils/photoUrl';

// ── Scenarios the user can preview ────────────────────────────────────────────
const SCENARIOS = [
  {
    id: 'new_lead',
    label: 'New Lead',
    icon: 'flash',
    message: "Hey, I saw your dealership online and I'm interested in trading in my truck. What does that process look like?",
  },
  {
    id: 'follow_up',
    label: 'Follow-Up',
    icon: 'refresh-circle',
    message: "Hey, just checking in. Still thinking about making a move on that vehicle we talked about?",
  },
  {
    id: 'happy_customer',
    label: 'Happy Customer',
    icon: 'happy',
    message: "Just wanted to say I love the car! Everyone keeps asking about it. You guys were amazing.",
  },
  {
    id: 'review_request',
    label: 'Review Ask',
    icon: 'star',
    message: "Someone just left me a 5-star review and mentioned you personally. How do I get more of those?",
  },
];

// ── Persona field definitions for completeness scoring ────────────────────────
const PERSONA_FIELDS: { key: string; label: string; weight: number }[] = [
  { key: 'bio',             label: 'Your story',         weight: 3 },
  { key: 'specialties',     label: 'Specialties',         weight: 2 },
  { key: 'tone',            label: 'Communication tone',  weight: 2 },
  { key: 'hobbies',         label: 'Hobbies',             weight: 1 },
  { key: 'years_experience',label: 'Years of experience', weight: 1 },
  { key: 'ideal_customer',  label: 'Ideal customer',      weight: 1 },
  { key: 'never_say',       label: 'Things I never say',  weight: 2 },
  { key: 'family_info',     label: 'Family background',   weight: 1 },
  { key: 'vehicles',        label: 'Vehicles & lifestyle',weight: 1 },
  { key: 'personal_motto',  label: 'Personal motto',      weight: 1 },
  { key: 'humor_level',     label: 'Humor style',         weight: 1 },
];
const MAX_WEIGHT = PERSONA_FIELDS.reduce((s, f) => s + f.weight, 0);

function getCompleteness(persona: any): { score: number; filled: typeof PERSONA_FIELDS; empty: typeof PERSONA_FIELDS } {
  if (!persona) return { score: 0, filled: [], empty: PERSONA_FIELDS };
  let earned = 0;
  const filled: typeof PERSONA_FIELDS = [];
  const empty:  typeof PERSONA_FIELDS = [];
  for (const f of PERSONA_FIELDS) {
    const val = persona[f.key];
    const has  = Array.isArray(val) ? val.length > 0 : Boolean(val && String(val).trim().length > 0);
    if (has) { earned += f.weight; filled.push(f); }
    else empty.push(f);
  }
  return { score: Math.round((earned / MAX_WEIGHT) * 100), filled, empty };
}

function scoreLabel(score: number) {
  if (score >= 90) return { text: 'Expert clone — sounds exactly like you', color: '#34C759' };
  if (score >= 70) return { text: 'Strong — a few more details will make it perfect', color: '#C9A962' };
  if (score >= 40) return { text: 'Getting there — your VA needs more context', color: '#FF9500' };
  return { text: 'Just started — your VA is speaking generically', color: '#FF3B30' };
}

// ── Tone / style display helpers ──────────────────────────────────────────────
const TONE_LABELS: Record<string, string>   = { professional: 'Professional', friendly: 'Friendly', casual: 'Casual', formal: 'Formal' };
const HUMOR_LABELS: Record<string, string>  = { none: 'No humor', light: 'Light wit', moderate: 'Playful', some: 'Some humor', lots: 'Lots of humor' };
const LENGTH_LABELS: Record<string, string> = { brief: 'Brief (1-2 sentences)', balanced: 'Balanced (2-3 sentences)', detailed: 'Detailed' };
const EMOJI_LABELS: Record<string, string>  = { never: 'No emojis', minimal: 'Minimal', moderate: 'Moderate', frequent: 'Frequent', light: 'Light' };

export default function VirtualAssistantScreen() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();

  const [persona, setPersona] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedScenario, setSelectedScenario] = useState(SCENARIOS[0]);
  const [generating, setGenerating] = useState(false);
  const [sampleReply, setSampleReply] = useState<string | null>(null);
  const [showAllEmpty, setShowAllEmpty] = useState(false);

  useEffect(() => { loadPersona(); }, [user?._id]);

  const loadPersona = async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/users/${user._id}/persona`);
      setPersona(res.data || {});
    } catch {
      setPersona({});
    } finally {
      setLoading(false);
    }
  };

  const generateSample = useCallback(async () => {
    if (!user?._id) return;
    setGenerating(true);
    setSampleReply(null);
    try {
      const res = await api.post(`/auth/persona/${user._id}/sample-message`, {
        scenario: selectedScenario.message,
      });
      setSampleReply(res.data.reply);
    } catch {
      setSampleReply("Couldn't generate a preview right now. Try again in a moment.");
    } finally {
      setGenerating(false);
    }
  }, [user?._id, selectedScenario]);

  if (loading) {
    return (
      <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="large" color="#C9A962" />
      </SafeAreaView>
    );
  }

  const { score, filled, empty } = getCompleteness(persona);
  const label = scoreLabel(score);
  const firstName = (user?.name || 'Your').split(' ')[0];
  const photoUrl  = resolveUserPhotoUrl(user);

  // Visible traits
  const traitChips = [
    persona?.tone         && { text: TONE_LABELS[persona.tone]   || persona.tone,         icon: 'mic'          },
    persona?.humor_level  && { text: HUMOR_LABELS[persona.humor_level] || persona.humor_level, icon: 'happy'        },
    persona?.response_length && { text: LENGTH_LABELS[persona.response_length] || persona.response_length, icon: 'text' },
    persona?.emoji_usage  && { text: EMOJI_LABELS[persona.emoji_usage] || persona.emoji_usage, icon: 'happy-outline' },
  ].filter(Boolean) as { text: string; icon: string }[];

  const emptyToShow = showAllEmpty ? empty : empty.slice(0, 3);

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>My VA</Text>
        <TouchableOpacity
          onPress={() => router.push('/settings/persona')}
          style={s.editBtn}
          data-testid="edit-va-btn"
        >
          <Ionicons name="create-outline" size={22} color="#C9A962" />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>

        {/* Identity Card */}
        <View style={s.identityCard}>
          <View style={s.avatarWrap}>
            {photoUrl
              ? <Image source={{ uri: photoUrl }} style={s.avatar} />
              : (
                <View style={[s.avatar, s.avatarFallback]}>
                  <Text style={s.avatarInitials}>{firstName.charAt(0).toUpperCase()}</Text>
                </View>
              )
            }
            <View style={[s.statusDot, { backgroundColor: score >= 40 ? '#34C759' : '#FF9500' }]} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.vaName}>{firstName}'s VA</Text>
            <Text style={s.vaSubtitle}>Personal AI Clone · Assist Mode</Text>
          </View>
          <View style={s.paBadge}>
            <Text style={s.paBadgeText}>PERSONAL AI</Text>
          </View>
        </View>

        {/* Completeness */}
        <View style={s.completenessCard}>
          <View style={s.completenessRow}>
            <Text style={s.completenessTitle}>Your VA knows {filled.length} of {PERSONA_FIELDS.length} things about you</Text>
            <Text style={[s.completenessScore, { color: label.color }]}>{score}%</Text>
          </View>
          <View style={s.progressTrack}>
            <View style={[s.progressFill, { width: `${score}%` as any, backgroundColor: label.color }]} />
          </View>
          <Text style={[s.completenessLabel, { color: label.color }]}>{label.text}</Text>
        </View>

        {/* Personality Chips */}
        {traitChips.length > 0 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>How Your VA Communicates</Text>
            <View style={s.chipsRow}>
              {traitChips.map((chip, i) => (
                <View key={i} style={s.chip}>
                  <Ionicons name={chip.icon as any} size={13} color="#C9A962" />
                  <Text style={s.chipText}>{chip.text}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* What Your VA Knows */}
        <View style={s.section}>
          <Text style={s.sectionTitle}>What Your VA Knows</Text>

          {persona?.bio ? (
            <View style={[s.knowledgeCard, { borderLeftColor: '#34C759' }]}>
              <Text style={s.knowledgeLabel}>Your Story</Text>
              <Text style={s.knowledgeValue} numberOfLines={3}>{persona.bio}</Text>
            </View>
          ) : null}

          {persona?.specialties?.length > 0 && (
            <View style={[s.knowledgeCard, { borderLeftColor: '#007AFF' }]}>
              <Text style={s.knowledgeLabel}>Specialties</Text>
              <Text style={s.knowledgeValue}>{persona.specialties.join(', ')}</Text>
            </View>
          )}

          {persona?.hobbies?.length > 0 && (
            <View style={[s.knowledgeCard, { borderLeftColor: '#AF52DE' }]}>
              <Text style={s.knowledgeLabel}>Hobbies & Interests</Text>
              <Text style={s.knowledgeValue}>{persona.hobbies.join(', ')}</Text>
            </View>
          )}

          {persona?.never_say ? (
            <View style={[s.knowledgeCard, { borderLeftColor: '#FF3B30' }]}>
              <Text style={s.knowledgeLabel}>Never Says</Text>
              <Text style={s.knowledgeValue}>{persona.never_say}</Text>
            </View>
          ) : null}

          {persona?.custom_phrases ? (
            <View style={[s.knowledgeCard, { borderLeftColor: '#FF9500' }]}>
              <Text style={s.knowledgeLabel}>Go-To Phrases</Text>
              <Text style={s.knowledgeValue}>{persona.custom_phrases}</Text>
            </View>
          ) : null}

          {persona?.ideal_customer ? (
            <View style={[s.knowledgeCard, { borderLeftColor: '#34C759' }]}>
              <Text style={s.knowledgeLabel}>Ideal Customer</Text>
              <Text style={s.knowledgeValue}>{persona.ideal_customer}</Text>
            </View>
          ) : null}

          {/* Empty fields nudge */}
          {empty.length > 0 && (
            <View style={s.emptySection}>
              <Text style={s.emptySectionTitle}>Your VA is missing these — add them to improve:</Text>
              {emptyToShow.map((f, i) => (
                <View key={i} style={s.emptyRow}>
                  <Ionicons name="ellipse-outline" size={14} color={colors.textSecondary} />
                  <Text style={s.emptyLabel}>{f.label}</Text>
                </View>
              ))}
              {empty.length > 3 && (
                <TouchableOpacity onPress={() => setShowAllEmpty(v => !v)}>
                  <Text style={{ fontSize: 13, color: '#C9A962', marginTop: 6 }}>
                    {showAllEmpty ? 'Show less' : `+${empty.length - 3} more`}
                  </Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={s.addInfoBtn} onPress={() => router.push('/settings/persona')}>
                <Ionicons name="add-circle" size={16} color="#C9A962" />
                <Text style={s.addInfoBtnText}>Add missing info</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Live Preview */}
        <View style={s.section}>
          <Text style={s.sectionTitle}>Hear Your VA in Action</Text>
          <Text style={s.sectionSub}>Pick a scenario and see exactly how your VA would respond.</Text>

          {/* Scenario selector */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -20, paddingHorizontal: 20 }} contentContainerStyle={{ gap: 10, paddingRight: 20 }}>
            {SCENARIOS.map(sc => (
              <TouchableOpacity
                key={sc.id}
                style={[s.scenarioPill, selectedScenario.id === sc.id && s.scenarioPillActive]}
                onPress={() => { setSelectedScenario(sc); setSampleReply(null); }}
              >
                <Ionicons name={sc.icon as any} size={14} color={selectedScenario.id === sc.id ? '#000' : '#C9A962'} />
                <Text style={[s.scenarioPillText, selectedScenario.id === sc.id && s.scenarioPillTextActive]}>
                  {sc.label}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Scenario message shown as "customer text" */}
          <View style={s.customerBubble}>
            <Text style={s.customerBubbleLabel}>Customer says:</Text>
            <Text style={s.customerBubbleText}>"{selectedScenario.message}"</Text>
          </View>

          {/* Generate button */}
          <TouchableOpacity
            style={[s.generateBtn, generating && { opacity: 0.7 }]}
            onPress={generateSample}
            disabled={generating}
            data-testid="generate-sample-btn"
          >
            {generating
              ? <ActivityIndicator size="small" color="#000" />
              : <><Ionicons name="sparkles" size={18} color="#000" /><Text style={s.generateBtnText}>Generate Your VA's Reply</Text></>
            }
          </TouchableOpacity>

          {/* AI Reply bubble */}
          {sampleReply && (
            <View style={s.replyWrap}>
              <View style={s.replyHeader}>
                {photoUrl
                  ? <Image source={{ uri: photoUrl }} style={s.replyAvatar} />
                  : <View style={[s.replyAvatar, s.avatarFallback]}><Text style={{ color: '#000', fontWeight: '700', fontSize: 13 }}>{firstName.charAt(0)}</Text></View>
                }
                <View>
                  <Text style={s.replyName}>{firstName}'s VA</Text>
                  <Text style={s.replyMeta}>AI-drafted · Assist mode</Text>
                </View>
              </View>
              <View style={s.replyBubble}>
                <Text style={s.replyText}>{sampleReply}</Text>
              </View>
              <Text style={s.replyDisclaimer}>This is how your VA would reply — you review and send.</Text>
            </View>
          )}
        </View>

        {/* How it works note */}
        <View style={[s.section, s.infoBox]}>
          <Ionicons name="information-circle" size={20} color="#C9A962" style={{ marginBottom: 8 }} />
          <Text style={s.infoTitle}>How Your VA Works</Text>
          <Text style={s.infoText}>
            When a customer texts, your VA drafts a reply in your voice. You see it pre-loaded in the composer, read it, and tap Send. The customer hears you — even when you're busy.
          </Text>
          <Text style={[s.infoText, { marginTop: 10, color: '#C9A962' }]}>
            The more info you add, the more it sounds like you.
          </Text>
        </View>

        {/* Edit profile CTA */}
        <TouchableOpacity
          style={s.editProfileBtn}
          onPress={() => router.push('/settings/persona')}
          data-testid="edit-profile-btn"
        >
          <Ionicons name="create" size={20} color="#000" />
          <Text style={s.editProfileBtnText}>Edit Your VA Profile</Text>
        </TouchableOpacity>

        <View style={{ height: 48 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container:          { flex: 1, backgroundColor: colors.bg },
  header:             { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn:            { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  editBtn:            { width: 36, height: 36, borderRadius: 18, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center' },
  headerTitle:        { fontSize: 17, fontWeight: '700', color: colors.text },
  content:            { padding: 20, paddingBottom: 60 },

  // Identity
  identityCard:       { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: colors.card, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: '#C9A96240' },
  avatarWrap:         { position: 'relative' },
  avatar:             { width: 54, height: 54, borderRadius: 27, borderWidth: 2, borderColor: '#C9A962' },
  avatarFallback:     { backgroundColor: '#C9A96240', alignItems: 'center', justifyContent: 'center' },
  avatarInitials:     { fontSize: 20, fontWeight: '800', color: '#C9A962' },
  statusDot:          { position: 'absolute', bottom: 1, right: 1, width: 14, height: 14, borderRadius: 7, borderWidth: 2, borderColor: colors.card },
  vaName:             { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 3 },
  vaSubtitle:         { fontSize: 13, color: colors.textSecondary },
  paBadge:            { backgroundColor: '#C9A96225', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1, borderColor: '#C9A962' },
  paBadgeText:        { fontSize: 11, fontWeight: '800', color: '#C9A962', letterSpacing: 0.8 },

  // Completeness
  completenessCard:   { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  completenessRow:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  completenessTitle:  { fontSize: 15, fontWeight: '600', color: colors.text, flex: 1, marginRight: 8 },
  completenessScore:  { fontSize: 20, fontWeight: '800' },
  progressTrack:      { height: 8, backgroundColor: colors.border, borderRadius: 4, overflow: 'hidden', marginBottom: 8 },
  progressFill:       { height: '100%', borderRadius: 4 },
  completenessLabel:  { fontSize: 13, fontWeight: '500' },

  // Section
  section:            { marginBottom: 24 },
  sectionTitle:       { fontSize: 17, fontWeight: '700', color: colors.text, marginBottom: 6 },
  sectionSub:         { fontSize: 13, color: colors.textSecondary, marginBottom: 14 },

  // Chips
  chipsRow:           { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip:               { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#C9A96218', borderRadius: 20, paddingHorizontal: 12, paddingVertical: 7, borderWidth: 1, borderColor: '#C9A96240' },
  chipText:           { fontSize: 13, fontWeight: '600', color: colors.text },

  // Knowledge cards
  knowledgeCard:      { backgroundColor: colors.card, borderRadius: 12, padding: 14, marginBottom: 8, borderLeftWidth: 3 },
  knowledgeLabel:     { fontSize: 11, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 },
  knowledgeValue:     { fontSize: 15, color: colors.text, lineHeight: 21 },

  // Empty fields
  emptySection:       { backgroundColor: colors.card, borderRadius: 12, padding: 14, marginTop: 8, borderWidth: 1, borderColor: colors.border },
  emptySectionTitle:  { fontSize: 13, color: colors.textSecondary, marginBottom: 10 },
  emptyRow:           { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  emptyLabel:         { fontSize: 13, color: colors.textSecondary },
  addInfoBtn:         { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, alignSelf: 'flex-start', backgroundColor: '#C9A96218', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  addInfoBtnText:     { fontSize: 13, fontWeight: '600', color: '#C9A962' },

  // Preview
  scenarioPill:       { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colors.card, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 9, borderWidth: 1.5, borderColor: '#C9A96240', marginBottom: 14 },
  scenarioPillActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  scenarioPillText:   { fontSize: 13, fontWeight: '600', color: '#C9A962' },
  scenarioPillTextActive: { color: '#000' },
  customerBubble:     { backgroundColor: colors.card, borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: colors.border },
  customerBubbleLabel:{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 },
  customerBubbleText: { fontSize: 15, color: colors.text, lineHeight: 21, fontStyle: 'italic' },
  generateBtn:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', borderRadius: 14, padding: 16 },
  generateBtnText:    { fontSize: 16, fontWeight: '700', color: '#000' },

  replyWrap:          { marginTop: 16 },
  replyHeader:        { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  replyAvatar:        { width: 36, height: 36, borderRadius: 18, borderWidth: 2, borderColor: '#C9A962', backgroundColor: '#C9A96240', alignItems: 'center', justifyContent: 'center' },
  replyName:          { fontSize: 15, fontWeight: '700', color: colors.text },
  replyMeta:          { fontSize: 12, color: '#C9A962' },
  replyBubble:        { backgroundColor: '#C9A96220', borderRadius: 16, borderTopLeftRadius: 4, padding: 16, borderWidth: 1, borderColor: '#C9A96240' },
  replyText:          { fontSize: 16, color: colors.text, lineHeight: 23 },
  replyDisclaimer:    { fontSize: 12, color: colors.textSecondary, marginTop: 8, textAlign: 'center', fontStyle: 'italic' },

  // Info box
  infoBox:            { backgroundColor: '#C9A96210', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#C9A96230', alignItems: 'center' },
  infoTitle:          { fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 8 },
  infoText:           { fontSize: 13, color: colors.textSecondary, lineHeight: 21, textAlign: 'center' },

  // Edit CTA
  editProfileBtn:     { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', borderRadius: 14, padding: 17, marginTop: 8 },
  editProfileBtnText: { fontSize: 16, fontWeight: '700', color: '#000' },
});
