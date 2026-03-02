import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Alert, Switch, Image, Platform, Linking,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

const SOCIAL_ICONS: Record<string, { name: string; color: string }> = {
  'logo-instagram': { name: 'logo-instagram', color: '#E4405F' },
  'logo-facebook': { name: 'logo-facebook', color: '#1877F2' },
  'logo-tiktok': { name: 'logo-tiktok', color: '#000' },
  'logo-linkedin': { name: 'logo-linkedin', color: '#0A66C2' },
  'logo-youtube': { name: 'logo-youtube', color: '#FF0000' },
  'logo-twitter': { name: 'logo-twitter', color: '#000' },
  'call': { name: 'call', color: '#34C759' },
  'mail': { name: 'mail', color: '#007AFF' },
  'card': { name: 'card', color: '#C9A962' },
  'star': { name: 'star', color: '#FBBC04' },
  'globe': { name: 'globe-outline', color: '#8E8E93' },
  'link': { name: 'link', color: '#8E8E93' },
};

interface LinkItem {
  id: string;
  label: string;
  url: string;
  icon: string;
  color: string;
  visible: boolean;
}

export default function EditLinkPage() {
  const router = useRouter();
  const user = useAuthStore(s => s.user);
  const colors = useThemeStore(s => s.colors);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [links, setLinks] = useState<LinkItem[]>([]);
  const [customLinks, setCustomLinks] = useState<LinkItem[]>([]);
  const [theme, setTheme] = useState('dark');
  const [accentColor, setAccentColor] = useState('#C9A962');
  const [views, setViews] = useState(0);
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);

  useEffect(() => { if (user?._id) loadPage(); }, [user?._id]);

  const loadPage = async () => {
    try {
      const res = await api.get(`/linkpage/user/${user?._id}`);
      const d = res.data;
      setUsername(d.username || '');
      setDisplayName(d.display_name || '');
      setBio(d.bio || '');
      setLinks(d.links || []);
      setCustomLinks(d.custom_links || []);
      setTheme(d.theme || 'dark');
      setAccentColor(d.accent_color || '#C9A962');
      setViews(d.views || 0);
    } catch (e) {
      Alert.alert('Error', 'Failed to load link page');
    } finally { setLoading(false); }
  };

  const checkUsername = useCallback(async (name: string) => {
    if (name.length < 3) { setUsernameAvailable(null); return; }
    try {
      const res = await api.post(`/linkpage/user/${user?._id}/check-username`, { username: name });
      setUsernameAvailable(res.data.available);
    } catch { setUsernameAvailable(null); }
  }, [user?._id]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/linkpage/user/${user?._id}`, {
        username, display_name: displayName, bio,
        links, custom_links: customLinks, theme, accent_color: accentColor,
      });
      Alert.alert('Saved!', 'Your link page has been updated.');
    } catch (e: any) {
      Alert.alert('Error', e.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const toggleLink = (id: string) => {
    setLinks(prev => prev.map(l => l.id === id ? { ...l, visible: !l.visible } : l));
  };

  const addCustomLink = () => {
    setCustomLinks(prev => [...prev, { id: `custom_${Date.now()}`, label: '', url: '', icon: 'globe', color: '#8E8E93', visible: true }]);
  };

  const updateCustomLink = (id: string, field: string, value: string) => {
    setCustomLinks(prev => prev.map(l => l.id === id ? { ...l, [field]: value } : l));
  };

  const removeCustomLink = (id: string) => {
    setCustomLinks(prev => prev.filter(l => l.id !== id));
  };

  const copyLink = () => {
    const url = `https://app.imosapp.com/l/${username}`;
    if (Platform.OS === 'web') {
      navigator.clipboard.writeText(url);
      Alert.alert('Copied!', url);
    } else {
      Linking.openURL(url);
    }
  };

  if (loading) return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]}><ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} /></SafeAreaView>
  );

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <View style={[s.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="linkpage-back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.text }]}>My Link Page</Text>
        <TouchableOpacity onPress={handleSave} disabled={saving} data-testid="linkpage-save">
          {saving ? <ActivityIndicator size="small" color={colors.accent} /> : <Text style={{ color: colors.accent, fontSize: 16, fontWeight: '700' }}>Save</Text>}
        </TouchableOpacity>
      </View>

      <ScrollView style={s.content} showsVerticalScrollIndicator={false}>
        {/* URL Preview + Copy */}
        <TouchableOpacity style={[s.urlCard, { backgroundColor: colors.card, borderColor: colors.border }]} onPress={copyLink} data-testid="linkpage-copy-url">
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 11, color: colors.textSecondary, fontWeight: '600', marginBottom: 2 }}>YOUR LINK</Text>
            <Text style={{ fontSize: 15, color: colors.accent, fontWeight: '700' }}>app.imosapp.com/l/{username}</Text>
          </View>
          <View style={[s.copyBadge, { backgroundColor: `${colors.accent}20` }]}>
            <Ionicons name="copy-outline" size={16} color={colors.accent} />
            <Text style={{ color: colors.accent, fontSize: 12, fontWeight: '700' }}>Copy</Text>
          </View>
        </TouchableOpacity>

        <Text style={[s.statsText, { color: colors.textSecondary }]}>{views} page views</Text>

        {/* Username */}
        <Text style={[s.sectionTitle, { color: colors.textSecondary }]}>USERNAME</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <TextInput
            style={[s.input, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border, flex: 1 }]}
            value={username}
            onChangeText={v => { setUsername(v.toLowerCase().replace(/[^a-z0-9.]/g, '')); checkUsername(v); }}
            placeholder="forestward"
            placeholderTextColor={colors.textTertiary}
            autoCapitalize="none"
            data-testid="linkpage-username"
          />
          {usernameAvailable !== null && (
            <Ionicons name={usernameAvailable ? 'checkmark-circle' : 'close-circle'} size={22} color={usernameAvailable ? '#34C759' : '#FF3B30'} />
          )}
        </View>

        {/* Display Name & Bio */}
        <Text style={[s.sectionTitle, { color: colors.textSecondary }]}>PROFILE</Text>
        <TextInput
          style={[s.input, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
          value={displayName}
          onChangeText={setDisplayName}
          placeholder="Display Name"
          placeholderTextColor={colors.textTertiary}
          data-testid="linkpage-name"
        />
        <TextInput
          style={[s.input, s.multiline, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
          value={bio}
          onChangeText={setBio}
          placeholder="Short bio or tagline..."
          placeholderTextColor={colors.textTertiary}
          multiline
          numberOfLines={3}
          data-testid="linkpage-bio"
        />

        {/* Theme */}
        <Text style={[s.sectionTitle, { color: colors.textSecondary }]}>THEME</Text>
        <View style={s.themeRow}>
          {(['dark', 'light'] as const).map(t => (
            <TouchableOpacity key={t} style={[s.themeBtn, theme === t && { borderColor: colors.accent, borderWidth: 2 }]} onPress={() => setTheme(t)} data-testid={`linkpage-theme-${t}`}>
              <View style={[s.themePreview, t === 'dark' ? { backgroundColor: '#000' } : { backgroundColor: '#F2F2F7' }]}>
                <View style={[s.themePreviewBar, { backgroundColor: t === 'dark' ? '#1C1C1E' : '#fff' }]} />
                <View style={[s.themePreviewBar, { backgroundColor: t === 'dark' ? '#1C1C1E' : '#fff', width: '70%' }]} />
              </View>
              <Text style={{ color: colors.text, fontSize: 12, fontWeight: '600', marginTop: 4 }}>{t === 'dark' ? 'Dark' : 'Light'}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Accent Color */}
        <Text style={[s.sectionTitle, { color: colors.textSecondary }]}>ACCENT COLOR</Text>
        <View style={s.colorRow}>
          {['#C9A962', '#007AFF', '#FF2D55', '#34C759', '#AF52DE', '#FF9500', '#5AC8FA', '#FF6B6B'].map(c => (
            <TouchableOpacity key={c} style={[s.colorDot, { backgroundColor: c }, accentColor === c && s.colorDotActive]} onPress={() => setAccentColor(c)} data-testid={`linkpage-color-${c}`} />
          ))}
        </View>

        {/* Links */}
        <Text style={[s.sectionTitle, { color: colors.textSecondary }]}>LINKS</Text>
        {links.map(link => {
          const iconInfo = SOCIAL_ICONS[link.icon] || SOCIAL_ICONS['link'];
          return (
            <View key={link.id} style={[s.linkRow, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={[s.linkIconBox, { backgroundColor: `${link.color}18` }]}>
                <Ionicons name={iconInfo.name as any} size={18} color={link.color} />
              </View>
              <Text style={[s.linkLabel, { color: colors.text }]}>{link.label}</Text>
              <Switch
                value={link.visible}
                onValueChange={() => toggleLink(link.id)}
                trackColor={{ false: '#3A3A3C', true: `${colors.accent}60` }}
                thumbColor={link.visible ? colors.accent : '#8E8E93'}
              />
            </View>
          );
        })}

        {/* Custom Links */}
        <Text style={[s.sectionTitle, { color: colors.textSecondary }]}>CUSTOM LINKS</Text>
        {customLinks.map(link => (
          <View key={link.id} style={[s.customLinkCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <TextInput
                style={[s.customInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.border, flex: 1 }]}
                value={link.label}
                onChangeText={v => updateCustomLink(link.id, 'label', v)}
                placeholder="Label (e.g. My Website)"
                placeholderTextColor={colors.textTertiary}
              />
              <TouchableOpacity onPress={() => removeCustomLink(link.id)}>
                <Ionicons name="trash-outline" size={20} color="#FF3B30" />
              </TouchableOpacity>
            </View>
            <TextInput
              style={[s.customInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.border }]}
              value={link.url}
              onChangeText={v => updateCustomLink(link.id, 'url', v)}
              placeholder="https://..."
              placeholderTextColor={colors.textTertiary}
              autoCapitalize="none"
              keyboardType="url"
            />
          </View>
        ))}
        <TouchableOpacity style={[s.addBtn, { borderColor: colors.accent }]} onPress={addCustomLink} data-testid="linkpage-add-custom">
          <Ionicons name="add-circle-outline" size={18} color={colors.accent} />
          <Text style={{ color: colors.accent, fontSize: 14, fontWeight: '600' }}>Add Custom Link</Text>
        </TouchableOpacity>

        <View style={{ height: 60 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5 },
  backBtn: { padding: 4 },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', textAlign: 'center' },
  content: { flex: 1, paddingHorizontal: 16, paddingTop: 16 },
  urlCard: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 14, borderWidth: 1, gap: 12 },
  copyBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  statsText: { fontSize: 12, textAlign: 'center', marginTop: 8, marginBottom: 16 },
  sectionTitle: { fontSize: 11, fontWeight: '700', letterSpacing: 1.5, marginTop: 20, marginBottom: 8 },
  input: { padding: 12, borderRadius: 10, fontSize: 15, borderWidth: 1, marginBottom: 8 },
  multiline: { minHeight: 70, textAlignVertical: 'top' },
  themeRow: { flexDirection: 'row', gap: 12 },
  themeBtn: { flex: 1, borderRadius: 12, borderWidth: 1.5, borderColor: 'transparent', padding: 8, alignItems: 'center' },
  themePreview: { width: '100%', height: 60, borderRadius: 8, padding: 10, gap: 6 },
  themePreviewBar: { height: 8, borderRadius: 4, width: '90%' },
  colorRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  colorDot: { width: 32, height: 32, borderRadius: 16 },
  colorDotActive: { borderWidth: 3, borderColor: '#fff', shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 4 },
  linkRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 6 },
  linkIconBox: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  linkLabel: { flex: 1, fontSize: 14, fontWeight: '600' },
  customLinkCard: { padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 8 },
  customInput: { padding: 10, borderRadius: 8, fontSize: 14, borderWidth: 1 },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 12, borderRadius: 12, borderWidth: 1.5, borderStyle: 'dashed' },
});
