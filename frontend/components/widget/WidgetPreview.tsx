import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Linking } from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { tid } from '../inbox/ownership';
import { previewUrl, PreviewProps } from './previewUrl';

// Native: same stand-in page in a WebView.
export const WidgetPreview = ({ widgetKey, config, height = 420, colors }: PreviewProps) => {
  const [bust, setBust] = useState(0);
  const [src, setSrc] = useState(() => previewUrl(widgetKey, config, 0));
  const json = JSON.stringify(config);
  useEffect(() => { const t = setTimeout(() => setSrc(previewUrl(widgetKey, config, bust)), 500); return () => clearTimeout(t); }, [json, widgetKey, bust]);
  return (
    <View style={{ borderRadius: 16, overflow: 'hidden', borderWidth: 1, borderColor: colors.border, backgroundColor: '#f4f5f7' }} {...tid('widget-preview')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <Ionicons name="eye-outline" size={15} color={colors.textSecondary} />
        <Text style={{ flex: 1, fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>Live preview · tap the bubble, nothing real is sent</Text>
        <TouchableOpacity onPress={() => setBust(b => b + 1)} hitSlop={8} {...tid('widget-preview-reload')}><Ionicons name="refresh" size={16} color={colors.textSecondary} /></TouchableOpacity>
        <TouchableOpacity onPress={() => Linking.openURL(src)} hitSlop={8} {...tid('widget-preview-open')}><Ionicons name="open-outline" size={16} color={colors.textSecondary} /></TouchableOpacity>
      </View>
      <WebView source={{ uri: src }} style={{ height, backgroundColor: '#f4f5f7' }} javaScriptEnabled domStorageEnabled originWhitelist={['*']} />
    </View>
  );
};
