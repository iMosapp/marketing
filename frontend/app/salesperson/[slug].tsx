import React, { useState, useEffect } from 'react';
import { View, ActivityIndicator, Text, StyleSheet } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';
import { SEOHead } from '../../components/SEOHead';

/**
 * SEO-friendly salesperson page.
 * Resolves the slug → user_id, then redirects to the digital card page.
 * The SEOHead component injects meta tags for crawlers before the redirect.
 */
export default function SalespersonPage() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!slug) return;
    api.get(`/seo/user-by-slug/${slug}`)
      .then(res => {
        if (res.data.error) {
          setError(true);
        } else {
          setUserId(res.data.user_id);
          // Redirect to the actual card page
          router.replace(`/card/${res.data.user_id}`);
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [slug]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Salesperson not found</Text>
      </View>
    );
  }

  return (
    <View style={styles.center}>
      {userId && <SEOHead type="card" id={userId} />}
      <ActivityIndicator size="large" color="#007AFF" />
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#000',
  },
  errorText: {
    color: '#999',
    fontSize: 18,
  },
});
