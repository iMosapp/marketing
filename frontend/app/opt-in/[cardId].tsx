import React, { useState, useEffect } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, Image, ActivityIndicator,
  Platform, Switch,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { PoweredByFooter } from '../../components/PoweredByFooter';

const IS_WEB = Platform.OS === 'web';

export default function OptInPage() {
  const { cardId } = useLocalSearchParams();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [context, setContext] = useState<any>(null);
  const [showcase, setShowcase] = useState(true);
  const [socialMedia, setSocialMedia] = useState(false);
  const [includePhoto, setIncludePhoto] = useState(true);

  const accent = context?.store?.primary_color || '#C9A962';
  const storeName = context?.store?.name || 'our dealership';
  const salesName = context?.salesman?.name || 'your salesperson';
  const firstName = salesName.split(' ')[0];

  useEffect(() => {
    loadContext();
  }, [cardId]);

  const loadContext = async () => {
    try {
      const res = await api.get(`/opt-in/card/${cardId}`);
      setContext(res.data);
      if (res.data.existing_consent) {
        setShowcase(res.data.existing_consent.showcase);
        setSocialMedia(res.data.existing_consent.social_media);
        setIncludePhoto(res.data.existing_consent.include_photo);
        setSubmitted(true);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not load card info');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!showcase && !socialMedia) return;
    setSubmitting(true);
    try {
      await api.post(`/opt-in/submit/${cardId}`, {
        showcase,
        social_media: socialMedia,
        include_photo: includePhoto,
      });
      setSubmitted(true);
    } catch (err) {
      console.error('Submit error:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator size="large" color={accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={{ flex: 1, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
        <Ionicons name="alert-circle-outline" size={56} color="#FF453A" />
        <Text style={{ color: '#FFF', fontSize: 18, fontWeight: '600', marginTop: 16 }}>{error}</Text>
      </View>
    );
  }

  // --- SUCCESS / ALREADY CONSENTED ---
  if (submitted) {
    return (
      <ScrollView style={{ flex: 1, backgroundColor: '#000' }} contentContainerStyle={{ alignItems: 'center', padding: 24, paddingTop: 60 }}>
        {context?.store?.logo_url && (
          <Image source={{ uri: context.store.logo_url }} style={{ width: 100, height: 40, resizeMode: 'contain', marginBottom: 24 }} />
        )}
        <View style={{ width: 80, height: 80, borderRadius: 40, backgroundColor: '#34C75915', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
          <Ionicons name="checkmark-circle" size={52} color="#34C759" />
        </View>
        <Text style={{ color: '#FFF', fontSize: 24, fontWeight: '700', textAlign: 'center', marginBottom: 8 }}>
          You're All Set!
        </Text>
        <Text style={{ color: '#8E8E93', fontSize: 16, textAlign: 'center', lineHeight: 24, marginBottom: 24, maxWidth: 340 }}>
          Thank you for letting us share your experience. {firstName} and the team at {storeName} truly appreciate your support.
        </Text>

        <View style={{ backgroundColor: '#1C1C1E', borderRadius: 16, padding: 20, width: '100%', maxWidth: 400, marginBottom: 24 }}>
          <Text style={{ color: '#8E8E93', fontSize: 12, fontWeight: '700', letterSpacing: 1, marginBottom: 12 }}>YOUR PERMISSIONS</Text>
          <ConsentRow label="Featured on Showcase" active={showcase} accent={accent} />
          <ConsentRow label="Shared on Social Media" active={socialMedia} accent={accent} />
          <ConsentRow label="Photo Included" active={includePhoto} accent={accent} />
        </View>

        <Text style={{ color: '#3A3A3C', fontSize: 13, textAlign: 'center', lineHeight: 20, maxWidth: 340 }}>
          You can change your preferences anytime by revisiting this page or contacting {firstName} directly.
        </Text>

        <View style={{ marginTop: 32 }}>
          <PoweredByFooter />
        </View>
      </ScrollView>
    );
  }

  // --- CONSENT FORM ---
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: '#000' }}
      contentContainerStyle={{ alignItems: 'center', padding: 24, paddingTop: 48 }}
    >
      {/* Store Logo */}
      {context?.store?.logo_url && (
        <Image source={{ uri: context.store.logo_url }} style={{ width: 120, height: 48, resizeMode: 'contain', marginBottom: 20 }} />
      )}

      {/* Customer Photo Preview */}
      {context?.photo_url && (
        <View style={{ width: 96, height: 96, borderRadius: 48, borderWidth: 3, borderColor: accent, overflow: 'hidden', marginBottom: 16 }}>
          <Image source={{ uri: context.photo_url }} style={{ width: '100%', height: '100%' }} />
        </View>
      )}

      {/* Greeting */}
      <Text style={{ color: '#FFF', fontSize: 26, fontWeight: '700', textAlign: 'center', marginBottom: 6 }}>
        {context?.customer_name ? `Hey ${context.customer_name.split(' ')[0]}!` : 'Hey there!'}
      </Text>
      <Text style={{ color: '#8E8E93', fontSize: 16, textAlign: 'center', lineHeight: 24, maxWidth: 360, marginBottom: 28 }}>
        {firstName} at <Text style={{ color: accent, fontWeight: '600' }}>{storeName}</Text> would love to feature your experience. Here's what that means:
      </Text>

      {/* --- What You're Agreeing To --- */}
      <View style={{ backgroundColor: '#1C1C1E', borderRadius: 16, width: '100%', maxWidth: 420, overflow: 'hidden', marginBottom: 20 }}>
        <View style={{ padding: 20, paddingBottom: 16 }}>
          <Text style={{ color: '#FFF', fontSize: 17, fontWeight: '700', marginBottom: 4 }}>
            Share Your Experience
          </Text>
          <Text style={{ color: '#8E8E93', fontSize: 14, lineHeight: 21 }}>
            Choose how you'd like to be featured. You can change this anytime.
          </Text>
        </View>

        {/* Toggle: Showcase Page */}
        <ToggleRow
          icon="storefront-outline"
          iconColor="#5856D6"
          title="Feature on Showcase Page"
          description={`Your name and experience will appear on ${firstName}'s professional showcase — a page they share with future customers as social proof.`}
          value={showcase}
          onToggle={setShowcase}
          accent={accent}
        />

        {/* Toggle: Social Media */}
        <ToggleRow
          icon="share-social-outline"
          iconColor="#FF9500"
          title="Share on Social Media"
          description={`Allow ${storeName} to share your experience on platforms like Instagram, TikTok, and Facebook. Great for showing off your new ride!`}
          value={socialMedia}
          onToggle={setSocialMedia}
          accent={accent}
        />

        {/* Toggle: Include Photo */}
        {context?.photo_url && (
          <ToggleRow
            icon="camera-outline"
            iconColor="#34C759"
            title="Include My Photo"
            description="Your delivery photo can be used along with your experience. Uncheck this if you'd prefer text-only."
            value={includePhoto}
            onToggle={setIncludePhoto}
            accent={accent}
          />
        )}
      </View>

      {/* Fine Print */}
      <View style={{ backgroundColor: '#1C1C1E', borderRadius: 12, padding: 16, width: '100%', maxWidth: 420, marginBottom: 24 }}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10 }}>
          <Ionicons name="shield-checkmark-outline" size={18} color="#8E8E93" style={{ marginTop: 2 }} />
          <Text style={{ color: '#6E6E73', fontSize: 13, lineHeight: 20, flex: 1 }}>
            By tapping "I Agree," you grant <Text style={{ color: '#8E8E93' }}>{storeName}</Text> permission to use your name{context?.photo_url ? ', photo,' : ''} and experience for promotional purposes on the selected platforms. You may withdraw consent at any time by contacting {firstName} or revisiting this page. Your personal contact information (phone, email) will never be publicly displayed.
          </Text>
        </View>
      </View>

      {/* CTA Button */}
      <TouchableOpacity
        style={{
          backgroundColor: (!showcase && !socialMedia) ? '#333' : accent,
          paddingVertical: 16, paddingHorizontal: 40, borderRadius: 14,
          width: '100%', maxWidth: 420, alignItems: 'center',
          opacity: (!showcase && !socialMedia) ? 0.5 : 1,
        }}
        onPress={handleSubmit}
        disabled={(!showcase && !socialMedia) || submitting}
        data-testid="opt-in-submit-btn"
      >
        {submitting ? (
          <ActivityIndicator size="small" color="#000" />
        ) : (
          <Text style={{ color: '#000', fontSize: 17, fontWeight: '700' }}>
            I Agree — Feature My Experience
          </Text>
        )}
      </TouchableOpacity>

      {/* Decline */}
      <TouchableOpacity style={{ marginTop: 16, paddingVertical: 12 }}>
        <Text style={{ color: '#6E6E73', fontSize: 15 }}>No thanks, maybe later</Text>
      </TouchableOpacity>

      <View style={{ marginTop: 24, marginBottom: 16 }}>
        <PoweredByFooter />
      </View>
    </ScrollView>
  );
}

// --- Subcomponents ---

function ToggleRow({ icon, iconColor, title, description, value, onToggle, accent }: {
  icon: string; iconColor: string; title: string; description: string;
  value: boolean; onToggle: (v: boolean) => void; accent: string;
}) {
  return (
    <View style={{
      flexDirection: 'row', alignItems: 'flex-start', padding: 16,
      borderTopWidth: 0.5, borderTopColor: '#2C2C2E', gap: 12,
    }}>
      <View style={{
        width: 36, height: 36, borderRadius: 10, backgroundColor: iconColor + '18',
        alignItems: 'center', justifyContent: 'center', marginTop: 2,
      }}>
        <Ionicons name={icon as any} size={20} color={iconColor} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ color: '#FFF', fontSize: 15, fontWeight: '600', marginBottom: 4 }}>{title}</Text>
        <Text style={{ color: '#8E8E93', fontSize: 13, lineHeight: 19 }}>{description}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onToggle}
        trackColor={{ false: '#39393D', true: accent }}
        thumbColor="#FFF"
        style={{ marginTop: 4 }}
      />
    </View>
  );
}

function ConsentRow({ label, active, accent }: { label: string; active: boolean; accent: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 6 }}>
      <Ionicons
        name={active ? 'checkmark-circle' : 'close-circle'}
        size={20}
        color={active ? '#34C759' : '#48484A'}
        style={{ marginRight: 10 }}
      />
      <Text style={{ color: active ? '#FFF' : '#6E6E73', fontSize: 15 }}>{label}</Text>
    </View>
  );
}
