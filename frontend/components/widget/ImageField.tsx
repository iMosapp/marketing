import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, Image, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api, { API_BASE_URL } from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { Label, Hint, inputStyle } from '../inbox/InboxEditorParts';

type Props = { label: string; hint?: string; value: string; onChange: (url: string) => void; widgetId: string; target: 'avatar' | 'icon'; colors: any; testId: string; round?: boolean; showToast: (m: string, t?: any, d?: number) => void; canManage: boolean };

// /api/images/... from the backend -> an address the dealer's website can load (the widget runs on their domain).
export const absoluteApiUrl = (path: string) => {
  if (!path || /^https?:\/\//.test(path) || path.startsWith('data:')) return path;
  const origin = Platform.OS === 'web' && typeof window !== 'undefined' ? window.location.origin : API_BASE_URL.replace(/\/api\/?$/, '');
  return `${origin}${path.startsWith('/') ? '' : '/'}${path}`;
};

// Photo/logo for the widget: upload from the device (or paste an address). Round preview for the header avatar, square for the bubble icon.
export const ImageField = ({ label, hint, value, onChange, widgetId, target, colors, testId, round, showToast, canManage }: Props) => {
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState(false);
  const pickAndUpload = async () => {
    try {
      const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: true, aspect: [1, 1], quality: 0.9 });
      if (res.canceled || !res.assets?.[0]) return;
      setBusy(true);
      const asset = res.assets[0];
      const blob = await (await fetch(asset.uri)).blob();
      const form = new FormData();
      form.append('file', blob as any, asset.fileName || `${target}.png`);
      form.append('target', target);
      const up = (await api.post(`/widgets/${widgetId}/upload`, form)).data;
      onChange(absoluteApiUrl(up.url));
      showToast('Uploaded. Save to put it on your site.', 'success');
    } catch (e: any) { showToast(errText(e, 'Could not upload that image'), 'error', 3500); }
    finally { setBusy(false); }
  };
  const size = 56;
  return (
    <View {...tid(testId)}>
      <Label colors={colors} top>{label}</Label>
      {hint ? <Hint colors={colors}>{hint}</Hint> : null}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ width: size, height: size, borderRadius: round ? size / 2 : 14, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' }} {...tid(`${testId}-preview`)}>
          {value ? <Image source={{ uri: value }} style={{ width: size, height: size }} resizeMode="cover" /> : <Ionicons name={round ? 'person-outline' : 'image-outline'} size={22} color={colors.textSecondary} />}
        </View>
        {canManage ? (
          <TouchableOpacity onPress={pickAndUpload} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, height: 40, paddingHorizontal: 14, borderRadius: 20, backgroundColor: GOLD, opacity: busy ? 0.6 : 1 }} {...tid(`${testId}-upload`)}>
            {busy ? <ActivityIndicator size="small" color="#111" /> : <Ionicons name="cloud-upload-outline" size={18} color="#111" />}
            <Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>{value ? 'Replace' : 'Upload'}</Text>
          </TouchableOpacity>
        ) : null}
        {value && canManage ? <TouchableOpacity onPress={() => onChange('')} hitSlop={8} {...tid(`${testId}-remove`)}><Ionicons name="trash-outline" size={20} color="#FF3B30" /></TouchableOpacity> : null}
        <TouchableOpacity onPress={() => setManual(v => !v)} hitSlop={8} {...tid(`${testId}-manual-toggle`)}><Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{manual ? 'Hide address' : 'Paste an address'}</Text></TouchableOpacity>
      </View>
      {manual ? <TextInput value={value} onChangeText={v => onChange(v.trim())} placeholder="https://yoursite.com/logo.png" placeholderTextColor={colors.textSecondary} autoCapitalize="none" autoCorrect={false} style={[inputStyle(colors), { marginTop: 8 }]} {...tid(`${testId}-url`)} /> : null}
    </View>
  );
};
