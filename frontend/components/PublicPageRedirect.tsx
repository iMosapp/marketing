import React, { useEffect } from 'react';
import { View, ActivityIndicator, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';

const PROD_BASE = 'https://app.imonsocial.com';

// /card/{id}, /p/{id}, /card/store/{slug}, /p/store/{slug} are server-rendered under /api; this route only forwards there.
export function PublicPageRedirect({ kind, id }: { kind: 'card' | 'p' | 'card/store' | 'p/store'; id?: string }) {
  const router = useRouter();
  useEffect(() => {
    if (!id) return;
    if (Platform.OS === 'web') {
      window.location.replace(`/api/${kind}/${id}${window.location.search}`);
      return;
    }
    WebBrowser.openBrowserAsync(`${PROD_BASE}/api/${kind}/${id}?self_preview=1`).finally(() => {
      if (router.canGoBack()) router.back();
      else router.replace('/(tabs)/home' as any);
    });
  }, [id]);
  return (
    <View style={{ flex: 1, backgroundColor: '#0B0B0C', alignItems: 'center', justifyContent: 'center' }}>
      <ActivityIndicator color="#C9A962" />
    </View>
  );
}
