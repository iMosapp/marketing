import React from 'react';
import { Platform, View, Text } from 'react-native';
import { tid } from './shared';

const IS_WEB = Platform.OS === 'web';
let WebView: any = null;
if (!IS_WEB) { try { WebView = require('react-native-webview').WebView; } catch {} }

// Renders the exact email HTML the client receives: iframe on web, WebView on the phone.
export const EmailPreview = ({ html, height = 560, colors }: { html: string; height?: number; colors: any }) => {
  if (IS_WEB) {
    return (
      <View style={{ height, borderRadius: 14, overflow: 'hidden', borderWidth: 1, borderColor: colors.border, backgroundColor: '#f5f3ee' }} {...tid('email-preview')}>
        <iframe srcDoc={html} sandbox="" title="Email preview" style={{ width: '100%', height: '100%', border: 'none', background: '#f5f3ee' } as any} />
      </View>
    );
  }
  if (!WebView) return <Text style={{ fontSize: 13, color: colors.textSecondary }}>Preview is not available on this device.</Text>;
  return (
    <View style={{ height, borderRadius: 14, overflow: 'hidden', borderWidth: 1, borderColor: colors.border }} {...tid('email-preview')}>
      <WebView originWhitelist={['*']} source={{ html: `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0;background:#f5f3ee">${html}</body></html>` }}
        nestedScrollEnabled style={{ flex: 1, backgroundColor: '#f5f3ee' }} onShouldStartLoadWithRequest={(req: any) => req.url.startsWith('about:') || req.url.startsWith('data:')} />
    </View>
  );
};
