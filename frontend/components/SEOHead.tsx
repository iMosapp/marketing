import React, { useState, useEffect } from 'react';
import Head from 'expo-router/head';
import { Platform } from 'react-native';
import api from '../services/api';

interface SEOHeadProps {
  type: 'card' | 'link' | 'store';
  id: string;
}

/**
 * Dynamic SEO head tags for public pages.
 * Fetches meta data from /api/seo/meta/{type}/{id} and injects
 * title, description, OG tags, and Schema.org JSON-LD.
 * Also tracks page visits with UTM parameters.
 */
export function SEOHead({ type, id }: SEOHeadProps) {
  const [meta, setMeta] = useState<any>(null);

  useEffect(() => {
    if (!id) return;
    const endpoint = type === 'link'
      ? `/seo/meta/link/${id}`
      : type === 'store'
        ? `/seo/meta/store/${id}`
        : `/seo/meta/card/${id}`;
    api.get(endpoint).then(res => setMeta(res.data)).catch(() => {});
    
    // Track UTM visit
    if (Platform.OS === 'web') {
      try {
        const params = new URLSearchParams(window.location.search);
        const utm_source = params.get('utm_source');
        if (utm_source) {
          api.post('/seo/track-visit', {
            page_type: type,
            reference_id: id,
            utm_source,
            utm_medium: params.get('utm_medium') || '',
            utm_campaign: params.get('utm_campaign') || '',
            referrer: document.referrer || '',
            user_agent: navigator.userAgent || '',
          }).catch(() => {});
        }
      } catch {}
    }
  }, [type, id]);

  // Inject JSON-LD directly into the DOM (expo-router/head doesn't support script tags)
  useEffect(() => {
    if (!meta?.schema || Platform.OS !== 'web') return;
    const existing = document.querySelector('script[data-seo-jsonld]');
    if (existing) existing.remove();
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.setAttribute('data-seo-jsonld', 'true');
    script.textContent = JSON.stringify(meta.schema);
    document.head.appendChild(script);
    return () => { script.remove(); };
  }, [meta?.schema]);

  if (!meta || meta.error) return null;

  return (
    <Head>
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />

      {/* Open Graph */}
      <meta property="og:title" content={meta.title} />
      <meta property="og:description" content={meta.description} />
      <meta property="og:url" content={meta.url} />
      <meta property="og:type" content={meta.type === 'business' ? 'business.business' : 'profile'} />
      {meta.image && <meta property="og:image" content={meta.image} />}

      {/* Twitter Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={meta.title} />
      <meta name="twitter:description" content={meta.description} />
      {meta.image && <meta name="twitter:image" content={meta.image} />}

      {/* Canonical URL */}
      <link rel="canonical" href={meta.url} />
    </Head>
  );
}
