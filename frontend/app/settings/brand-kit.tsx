import React, {
  useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
  Image,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import api, { emailAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import { showAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
const DEFAULT_COLORS = [
  '#007AFF', '#34C759', '#FF9500', '#FF3B30', '#5856D6', 
  '#AF52DE', '#FF2D55', '#00C7BE', '#FFD60A', '#1C1C1E'
];

export default function BrandKitSettings() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);
  
  // Brand kit fields
  const [logoUrl, setLogoUrl] = useState('');
  const [primaryColor, setPrimaryColor] = useState('#007AFF');
  const [secondaryColor, setSecondaryColor] = useState('#34C759');
  const [accentColor, setAccentColor] = useState('#FFD60A');
  const [companyName, setCompanyName] = useState('');
  const [tagline, setTagline] = useState('');
  const [footerText, setFooterText] = useState("i'M On Social");
  const [pageTheme, setPageTheme] = useState<'light' | 'dark'>('dark');
  const [socialLinks, setSocialLinks] = useState({
    website: '',
    facebook: '',
    instagram: '',
    twitter: '',
    linkedin: '',
  });
  
  // Which entity type to save for
  const [entityType, setEntityType] = useState<'user' | 'store' | 'organization'>('user');

  useEffect(() => {
    if (user?._id) {
      loadBrandKit();
    } else {
      setLoading(false);
    }
  }, [user?._id]);

  const loadBrandKit = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      // Try to load user's brand kit first
      const brandKit = await emailAPI.getBrandKit('user', user._id);
      if (brandKit) {
        setLogoUrl(brandKit.logo_url || '');
        setPrimaryColor(brandKit.primary_color || '#007AFF');
        setSecondaryColor(brandKit.secondary_color || '#34C759');
        setAccentColor(brandKit.accent_color || '#FFD60A');
        setCompanyName(brandKit.company_name || '');
        setTagline(brandKit.tagline || '');
        setFooterText(brandKit.footer_text || "i'M On Social");
        setPageTheme(brandKit.page_theme === 'light' ? 'light' : 'dark');
        setSocialLinks(brandKit.social_links || {});
      }
    } catch (error) {
      console.log('No existing brand kit, using defaults');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!user?._id) return;
    
    try {
      setSaving(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      
      await emailAPI.updateBrandKit(entityType, user._id, {
        logo_url: logoUrl,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        accent_color: accentColor,
        company_name: companyName,
        tagline: tagline,
        footer_text: footerText,
        social_links: socialLinks,
        page_theme: pageTheme,
      });

      // Also sync logo_url to the store so emails pick it up
      if (logoUrl && user?.store_id) {
        try {
          await api.put(`/admin/stores/${user.store_id}`, { logo_url: logoUrl });
        } catch {}
      }
      
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      showToast('Brand kit saved successfully!');
    } catch (error) {
      console.error('Error saving brand kit:', error);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      showAlert('Error', 'Failed to save brand kit');
    } finally {
      setSaving(false);
    }
  };

  const handleUploadLogo = async () => {
    if (Platform.OS !== 'web') return;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e: any) => {
      const file = e.target.files[0];
      if (!file) return;
      setLogoUploading(true);
      try {
        const fd = new FormData();
        fd.append('file', file);
        const storeId = user?.store_id;
        const endpoint = storeId
          ? `/admin/stores/${storeId}/upload-logo`
          : `/admin/organizations/${user?.organization_id}/upload-logo`;
        const res = await api.post(endpoint, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        const url = res.data.logo_url || '';
        setLogoUrl(url);
        showToast('Logo uploaded!');
      } catch {
        showAlert('Error', 'Failed to upload logo');
      } finally {
        setLogoUploading(false);
      }
    };
    input.click();
  };

  /**
   * ColorPickerField — Uses native <input type="color"> on web (full wheel + dropper)
   * and a hex text field for manual entry. Works on iOS Safari, Chrome, and desktop.
   */
  const ColorPickerField = ({
    label,
    value,
    onSelect,
  }: {
    label: string;
    value: string;
    onSelect: (color: string) => void;
  }) => {
    const [hexInput, setHexInput] = useState(value);
    // Sync hex input when value changes externally
    React.useEffect(() => { setHexInput(value); }, [value]);

    const handleHexChange = (text: string) => {
      setHexInput(text);
      // Apply once it's a valid 6-digit hex
      if (/^#[0-9A-Fa-f]{6}$/.test(text)) {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        onSelect(text);
      }
    };

    const openNativePicker = () => {
      if (Platform.OS === 'web') {
        const input = document.createElement('input');
        input.type = 'color';
        input.value = /^#[0-9A-Fa-f]{6}$/.test(value) ? value : '#007AFF';
        input.style.position = 'absolute';
        input.style.opacity = '0';
        input.style.width = '0';
        input.style.height = '0';
        document.body.appendChild(input);
        input.addEventListener('input', (e: any) => {
          const col = e.target.value;
          setHexInput(col);
          onSelect(col);
        });
        input.addEventListener('change', () => document.body.removeChild(input));
        input.click();
      }
    };

    const QUICK_PICKS = [
      '#007AFF','#34C759','#FF9500','#FF3B30','#5856D6',
      '#AF52DE','#FF2D55','#00C7BE','#FFD60A','#C9A962',
      '#1877F2','#E1306C','#000000','#FFFFFF',
    ];

    return (
      <View style={styles.colorPickerContainer}>
        <Text style={styles.colorPickerLabel}>{label}</Text>

        {/* Main swatch + hex row */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          {/* Large tappable swatch — opens native color wheel */}
          <TouchableOpacity
            onPress={openNativePicker}
            activeOpacity={0.8}
            data-testid={`color-swatch-${label}`}
            style={{
              width: 52, height: 52, borderRadius: 14,
              backgroundColor: /^#[0-9A-Fa-f]{6}$/.test(value) ? value : '#007AFF',
              borderWidth: 2, borderColor: 'rgba(255,255,255,0.2)',
              alignItems: 'center', justifyContent: 'center',
              shadowColor: '#000', shadowOpacity: 0.3, shadowRadius: 4,
            }}
          >
            {Platform.OS === 'web' && (
              <Ionicons name="eyedrop-outline" size={20} color="rgba(255,255,255,0.8)" />
            )}
          </TouchableOpacity>

          {/* Hex input */}
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 4, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Hex Code
            </Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 10, borderWidth: 1, borderColor: /^#[0-9A-Fa-f]{6}$/.test(hexInput) ? hexInput + '60' : colors.border, overflow: 'hidden' }}>
              <View style={{ width: 28, height: 28, marginLeft: 8, borderRadius: 6, backgroundColor: /^#[0-9A-Fa-f]{6}$/.test(hexInput) ? hexInput : colors.border }} />
              <TextInput
                style={{ flex: 1, padding: 10, fontSize: 17, color: colors.text, fontFamily: 'monospace' }}
                value={hexInput}
                onChangeText={handleHexChange}
                placeholder="#000000"
                placeholderTextColor={colors.textSecondary}
                maxLength={7}
                autoCapitalize="characters"
                autoCorrect={false}
                data-testid={`color-hex-${label}`}
              />
            </View>
          </View>

          {/* Tap-to-pick hint (web only) */}
          {Platform.OS === 'web' && (
            <TouchableOpacity onPress={openNativePicker} style={{ alignItems: 'center', opacity: 0.6 }}>
              <Ionicons name="color-palette-outline" size={22} color={colors.textSecondary} />
              <Text style={{ fontSize: 10, color: colors.textSecondary, marginTop: 2 }}>Pick</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Quick-pick swatches */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={{ flexDirection: 'row', gap: 8, paddingBottom: 4 }}>
            {QUICK_PICKS.map((c) => (
              <TouchableOpacity
                key={c}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  setHexInput(c);
                  onSelect(c);
                }}
                style={{
                  width: 30, height: 30, borderRadius: 8,
                  backgroundColor: c,
                  borderWidth: value === c ? 2.5 : 1,
                  borderColor: value === c ? '#FFF' : 'rgba(255,255,255,0.15)',
                  alignItems: 'center', justifyContent: 'center',
                }}
              >
                {value === c && <Ionicons name="checkmark" size={14} color={c === '#FFFFFF' ? '#000' : '#FFF'} />}
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Brand Kit</Text>
        <TouchableOpacity onPress={handleSave} disabled={saving} style={styles.saveButton}>
          {saving ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <Text style={styles.saveText}>Save</Text>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Preview Card */}
        <View style={[styles.previewCard, { borderColor: primaryColor }]}>
          <View style={[styles.previewHeader, { backgroundColor: primaryColor }]}>
            {logoUrl ? (
              <Image source={{ uri: logoUrl }} style={styles.previewLogo} />
            ) : (
              <View style={styles.previewLogoPlaceholder}>
                <Ionicons name="business" size={24} color={colors.text} />
              </View>
            )}
            <Text style={styles.previewCompany}>{companyName || 'Your Company'}</Text>
            {tagline ? <Text style={styles.previewTagline}>{tagline}</Text> : null}
          </View>
          <View style={styles.previewBody}>
            <Text style={styles.previewBodyText}>Your email content will appear here...</Text>
          </View>
          <View style={styles.previewFooter}>
            <Text style={styles.previewFooterText}>{footerText}</Text>
          </View>
        </View>

        {/* Logo */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Logo</Text>
          {logoUrl ? (
            <View style={{ alignItems: 'center', marginBottom: 12 }}>
              <Image source={{ uri: logoUrl }} style={{ width: 160, height: 60, resizeMode: 'contain', borderRadius: 8 }} />
            </View>
          ) : null}
          <TouchableOpacity
            style={[styles.uploadButton, { borderColor: colors.border }]}
            onPress={handleUploadLogo}
            disabled={logoUploading}
            data-testid="upload-logo-btn"
          >
            {logoUploading ? (
              <ActivityIndicator size="small" color={colors.text} />
            ) : (
              <>
                <Ionicons name="cloud-upload-outline" size={20} color={colors.text} />
                <Text style={[styles.uploadButtonText, { color: colors.text }]}>
                  {logoUrl ? 'Change Logo' : 'Upload Logo'}
                </Text>
              </>
            )}
          </TouchableOpacity>
          <Text style={[styles.inputHelper, { color: colors.textSecondary }]}>Or paste a URL:</Text>
          <TextInput
            style={styles.input}
            placeholder="https://example.com/logo.png"
            placeholderTextColor={colors.textSecondary}
            value={logoUrl}
            onChangeText={setLogoUrl}
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>

        {/* Company Name */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Company Name</Text>
          <TextInput
            style={styles.input}
            placeholder="Your Company Name"
            placeholderTextColor={colors.textSecondary}
            value={companyName}
            onChangeText={setCompanyName}
          />
        </View>

        {/* Tagline */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Tagline</Text>
          <TextInput
            style={styles.input}
            placeholder="Your company tagline"
            placeholderTextColor={colors.textSecondary}
            value={tagline}
            onChangeText={setTagline}
          />
        </View>

        {/* Page Theme Toggle */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Public Page Theme</Text>
          <Text style={[styles.inputHelper, { color: colors.textSecondary, marginBottom: 12 }]}>
            Controls the look of your Digital Card, Link Page, and other public pages
          </Text>
          <View style={styles.themeToggleRow}>
            <TouchableOpacity
              style={[
                styles.themeToggleOption,
                pageTheme === 'dark' && styles.themeToggleActive,
                pageTheme === 'dark' && { borderColor: primaryColor },
              ]}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setPageTheme('dark');
              }}
              data-testid="theme-toggle-dark"
            >
              <View style={[styles.themePreviewDark]}>
                <View style={[styles.themePreviewAccent, { backgroundColor: primaryColor }]} />
              </View>
              <Text style={[styles.themeToggleLabel, pageTheme === 'dark' && { color: colors.text, fontWeight: '700' }]}>Dark</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.themeToggleOption,
                pageTheme === 'light' && styles.themeToggleActive,
                pageTheme === 'light' && { borderColor: primaryColor },
              ]}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setPageTheme('light');
              }}
              data-testid="theme-toggle-light"
            >
              <View style={[styles.themePreviewLight]}>
                <View style={[styles.themePreviewAccent, { backgroundColor: primaryColor }]} />
              </View>
              <Text style={[styles.themeToggleLabel, pageTheme === 'light' && { color: colors.text, fontWeight: '700' }]}>Light</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Colors */}
        <ColorPickerField label="Primary Color" value={primaryColor} onSelect={setPrimaryColor} />
        <ColorPickerField label="Secondary Color" value={secondaryColor} onSelect={setSecondaryColor} />
        <ColorPickerField label="Accent Color" value={accentColor} onSelect={setAccentColor} />

        {/* Footer Text */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Footer Text</Text>
          <TextInput
            style={styles.input}
            placeholder="i'M On Social"
            placeholderTextColor={colors.textSecondary}
            value={footerText}
            onChangeText={setFooterText}
          />
        </View>

        {/* Social Links */}
        <Text style={styles.sectionTitle}>Social Links</Text>
        
        <View style={styles.socialInputGroup}>
          <View style={styles.socialIcon}>
            <Ionicons name="globe" size={20} color="#007AFF" />
          </View>
          <TextInput
            style={styles.socialInput}
            placeholder="Website URL"
            placeholderTextColor={colors.textSecondary}
            value={socialLinks.website}
            onChangeText={(text) => setSocialLinks({ ...socialLinks, website: text })}
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>

        <View style={styles.socialInputGroup}>
          <View style={styles.socialIcon}>
            <Ionicons name="logo-facebook" size={20} color="#1877F2" />
          </View>
          <TextInput
            style={styles.socialInput}
            placeholder="Facebook URL"
            placeholderTextColor={colors.textSecondary}
            value={socialLinks.facebook}
            onChangeText={(text) => setSocialLinks({ ...socialLinks, facebook: text })}
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>

        <View style={styles.socialInputGroup}>
          <View style={styles.socialIcon}>
            <Ionicons name="logo-instagram" size={20} color="#E4405F" />
          </View>
          <TextInput
            style={styles.socialInput}
            placeholder="Instagram URL"
            placeholderTextColor={colors.textSecondary}
            value={socialLinks.instagram}
            onChangeText={(text) => setSocialLinks({ ...socialLinks, instagram: text })}
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>

        <View style={styles.socialInputGroup}>
          <View style={styles.socialIcon}>
            <Ionicons name="logo-twitter" size={20} color="#1DA1F2" />
          </View>
          <TextInput
            style={styles.socialInput}
            placeholder="Twitter/X URL"
            placeholderTextColor={colors.textSecondary}
            value={socialLinks.twitter}
            onChangeText={(text) => setSocialLinks({ ...socialLinks, twitter: text })}
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>

        <View style={styles.socialInputGroup}>
          <View style={styles.socialIcon}>
            <Ionicons name="logo-linkedin" size={20} color="#0A66C2" />
          </View>
          <TextInput
            style={styles.socialInput}
            placeholder="LinkedIn URL"
            placeholderTextColor={colors.textSecondary}
            value={socialLinks.linkedin}
            onChangeText={(text) => setSocialLinks({ ...socialLinks, linkedin: text })}
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>

        {/* Info */}
        <View style={styles.infoCard}>
          <Ionicons name="information-circle" size={20} color={colors.textSecondary} />
          <Text style={styles.infoText}>
            Your brand kit is applied to emails and public-facing pages like your Digital Card. 
            Use the Page Theme toggle to switch between light and dark looks.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 28,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  saveButton: {
    padding: 4,
  },
  saveText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  
  // Preview Card
  previewCard: {
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 24,
    borderWidth: 2,
  },
  previewHeader: {
    padding: 20,
    alignItems: 'center',
  },
  previewLogo: {
    width: 60,
    height: 60,
    borderRadius: 8,
    marginBottom: 8,
  },
  previewLogoPlaceholder: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  previewCompany: {
    fontSize: 19,
    fontWeight: '700',
    color: colors.text,
  },
  previewTagline: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 4,
  },
  previewBody: {
    padding: 20,
    backgroundColor: colors.card,
  },
  previewBodyText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
  previewFooter: {
    padding: 16,
    backgroundColor: '#F5F5F5',
    alignItems: 'center',
  },
  previewFooterText: {
    fontSize: 14,
    color: '#999',
  },

  // Inputs
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    fontSize: 18,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  uploadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    marginBottom: 8,
  },
  uploadButtonText: {
    fontSize: 17,
    fontWeight: '600',
  },
  inputHelper: {
    fontSize: 14,
    marginBottom: 6,
  },
  
  // Color Picker
  colorPickerContainer: {
    marginBottom: 20,
  },
  colorPickerLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
  },
  colorOptions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  colorOption: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  colorOptionSelected: {
    borderColor: colors.border,
  },
  customColorContainer: {
    marginLeft: 8,
  },
  customColorInput: {
    backgroundColor: colors.card,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 16,
    color: colors.text,
    borderWidth: 2,
    width: 90,
  },

  // Section
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 16,
    marginTop: 8,
  },

  // Social Inputs
  socialInputGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 12,
  },
  socialIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  socialInput: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    fontSize: 17,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },

  // Info Card
  infoCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    gap: 12,
    marginTop: 24,
    alignItems: 'flex-start',
  },
  infoText: {
    flex: 1,
    fontSize: 16,
    color: colors.textSecondary,
    lineHeight: 20,
  },

  // Theme Toggle
  themeToggleRow: {
    flexDirection: 'row',
    gap: 12,
  },
  themeToggleOption: {
    flex: 1,
    alignItems: 'center',
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.surface,
    padding: 12,
    backgroundColor: colors.card,
  },
  themeToggleActive: {
    borderWidth: 2,
  },
  themeToggleLabel: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textSecondary,
    marginTop: 8,
  },
  themePreviewDark: {
    width: '100%',
    height: 56,
    borderRadius: 8,
    backgroundColor: '#1A1A1A',
    alignItems: 'center',
    justifyContent: 'flex-end',
    padding: 8,
    overflow: 'hidden',
  },
  themePreviewLight: {
    width: '100%',
    height: 56,
    borderRadius: 8,
    backgroundColor: '#F5F5F5',
    alignItems: 'center',
    justifyContent: 'flex-end',
    padding: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  themePreviewAccent: {
    width: '60%',
    height: 6,
    borderRadius: 3,
  },
});
