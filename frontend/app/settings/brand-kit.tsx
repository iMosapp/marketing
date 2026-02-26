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
import { emailAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../components/common/Toast';

const DEFAULT_COLORS = [
  '#007AFF', '#34C759', '#FF9500', '#FF3B30', '#5856D6', 
  '#AF52DE', '#FF2D55', '#00C7BE', '#FFD60A', '#1C1C1E'
];

export default function BrandKitSettings() {
  const router = useRouter();
  const { user } = useAuthStore();
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Brand kit fields
  const [logoUrl, setLogoUrl] = useState('');
  const [primaryColor, setPrimaryColor] = useState('#007AFF');
  const [secondaryColor, setSecondaryColor] = useState('#34C759');
  const [accentColor, setAccentColor] = useState('#FFD60A');
  const [companyName, setCompanyName] = useState('');
  const [tagline, setTagline] = useState('');
  const [footerText, setFooterText] = useState('Powered by iMos');
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
        setFooterText(brandKit.footer_text || 'Powered by iMos');
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
      });
      
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      showToast('Brand kit saved successfully!');
    } catch (error) {
      console.error('Error saving brand kit:', error);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert('Error', 'Failed to save brand kit');
    } finally {
      setSaving(false);
    }
  };

  const ColorPicker = ({ 
    label, 
    value, 
    onSelect 
  }: { 
    label: string; 
    value: string; 
    onSelect: (color: string) => void;
  }) => (
    <View style={styles.colorPickerContainer}>
      <Text style={styles.colorPickerLabel}>{label}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={styles.colorOptions}>
          {DEFAULT_COLORS.map((color) => (
            <TouchableOpacity
              key={color}
              style={[
                styles.colorOption,
                { backgroundColor: color },
                value === color && styles.colorOptionSelected,
              ]}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                onSelect(color);
              }}
            >
              {value === color && (
                <Ionicons name="checkmark" size={16} color="#FFF" />
              )}
            </TouchableOpacity>
          ))}
          {/* Custom color input */}
          <View style={styles.customColorContainer}>
            <TextInput
              style={[styles.customColorInput, { borderColor: value }]}
              value={value}
              onChangeText={onSelect}
              placeholder="#000000"
              placeholderTextColor="#8E8E93"
              maxLength={7}
            />
          </View>
        </View>
      </ScrollView>
    </View>
  );

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
                <Ionicons name="business" size={24} color="#FFF" />
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

        {/* Logo URL */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Logo URL</Text>
          <TextInput
            style={styles.input}
            placeholder="https://example.com/logo.png"
            placeholderTextColor="#8E8E93"
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
            placeholderTextColor="#8E8E93"
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
            placeholderTextColor="#8E8E93"
            value={tagline}
            onChangeText={setTagline}
          />
        </View>

        {/* Colors */}
        <ColorPicker label="Primary Color" value={primaryColor} onSelect={setPrimaryColor} />
        <ColorPicker label="Secondary Color" value={secondaryColor} onSelect={setSecondaryColor} />
        <ColorPicker label="Accent Color" value={accentColor} onSelect={setAccentColor} />

        {/* Footer Text */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Footer Text</Text>
          <TextInput
            style={styles.input}
            placeholder="Powered by iMos"
            placeholderTextColor="#8E8E93"
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
            placeholderTextColor="#8E8E93"
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
            placeholderTextColor="#8E8E93"
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
            placeholderTextColor="#8E8E93"
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
            placeholderTextColor="#8E8E93"
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
            placeholderTextColor="#8E8E93"
            value={socialLinks.linkedin}
            onChangeText={(text) => setSocialLinks({ ...socialLinks, linkedin: text })}
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>

        {/* Info */}
        <View style={styles.infoCard}>
          <Ionicons name="information-circle" size={20} color="#8E8E93" />
          <Text style={styles.infoText}>
            Your brand kit will be applied to all emails sent from iMos. 
            The preview above shows how your email header and footer will look.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
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
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  saveButton: {
    padding: 4,
  },
  saveText: {
    fontSize: 16,
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
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
  },
  previewTagline: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 4,
  },
  previewBody: {
    padding: 20,
    backgroundColor: '#FFF',
  },
  previewBodyText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
  },
  previewFooter: {
    padding: 16,
    backgroundColor: '#F5F5F5',
    alignItems: 'center',
  },
  previewFooterText: {
    fontSize: 12,
    color: '#999',
  },

  // Inputs
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  
  // Color Picker
  colorPickerContainer: {
    marginBottom: 20,
  },
  colorPickerLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
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
    borderColor: '#FFF',
  },
  customColorContainer: {
    marginLeft: 8,
  },
  customColorInput: {
    backgroundColor: '#1C1C1E',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
    color: '#FFF',
    borderWidth: 2,
    width: 90,
  },

  // Section
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
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
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  socialInput: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    fontSize: 15,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },

  // Info Card
  infoCard: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    gap: 12,
    marginTop: 24,
    alignItems: 'flex-start',
  },
  infoText: {
    flex: 1,
    fontSize: 14,
    color: '#8E8E93',
    lineHeight: 20,
  },
});
