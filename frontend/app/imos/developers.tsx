import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, useWindowDimensions, Platform, ActivityIndicator, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';
import { ImosHeader, ImosFooter } from './_components';
import { MarkdownRenderer } from '../../components/docs/MarkdownRenderer';

type Doc = { slug: string; title: string; subtitle: string; content: string; download_url: string; updated_at: string | null };

const LIGHT = { text: '#1D1D1F', textSecondary: '#6E6E73', card: '#F5F5F7', border: '#E5E5EA' };
const ICONS: Record<string, string> = { 'api-reference': 'code-slash', 'crm-integration-guide': 'git-network', 'automotive-crm-programs': 'car-sport' };

const openUrl = (path: string) => {
  const url = path.startsWith('http') ? path : `${Platform.OS === 'web' ? '' : 'https://app.imonsocial.com'}${path}`;
  if (Platform.OS === 'web') window.open(url, '_blank');
  else Linking.openURL(url);
};

const QUICK = [
  { icon: 'play-circle', color: '#34C759', title: 'Try it live', desc: 'Interactive console. Paste your key under Authorize and run real calls.', cta: 'Open API console', path: '/api/public/reference', testid: 'dev-console-btn' },
  { icon: 'document-text', color: '#007AFF', title: 'OpenAPI 3 schema', desc: 'Import into Postman or Insomnia, or generate a client in any language.', cta: 'openapi-v1.json', path: '/api/public/openapi-v1.json', testid: 'dev-openapi-btn' },
  { icon: 'key', color: '#C9A962', title: 'Get an API key', desc: 'A dealership admin creates one in the app: Tools, Integrations, API Keys. One key = one store.', cta: 'Sign in to the app', path: '/imos/login', testid: 'dev-key-btn', internal: true },
];

export default function DevelopersPage() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 900;
  const params = useLocalSearchParams<{ doc?: string }>();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [active, setActive] = useState<string>((params.doc as string) || 'api-reference');

  useEffect(() => {
    api.get('/public/developer-docs').then(r => setDocs(r.data?.docs || [])).catch(() => setError('Could not load the documentation. Try again in a minute.')).finally(() => setLoading(false));
  }, []);
  useEffect(() => { if (params.doc) setActive(params.doc as string); }, [params.doc]);

  const doc = useMemo(() => docs.find(d => d.slug === active) || docs[0], [docs, active]);
  const pick = (slug: string) => { setActive(slug); router.setParams({ doc: slug } as any); };

  return (
    <ScrollView style={s.page} contentContainerStyle={{ flexGrow: 1 }} testID="developers-page">
      <ImosHeader />
      <View style={s.hero}>
        <View style={[s.heroInner, isDesktop && { maxWidth: 1200 }]}>
          <View style={s.eyebrowRow}><Ionicons name="terminal" size={14} color="#5856D6" /><Text style={s.eyebrow}>DEVELOPERS</Text></View>
          <Text style={s.h1} testID="developers-title">Build on I'm On Social</Text>
          <Text style={s.lead}>
            An open REST API and signed webhooks for every customer, text, call, note, task and sold record in a store. Connect your CRM, DMS, marketing stack or automation tool. No partnership paperwork: a dealership admin hands you a key and you are live.
          </Text>
          <View style={[s.quickRow, !isDesktop && { flexDirection: 'column' }]}>
            {QUICK.map(q => (
              <TouchableOpacity key={q.title} style={s.quickCard} onPress={() => (q.internal ? router.push(q.path as any) : openUrl(q.path))} testID={q.testid}>
                <View style={[s.quickIcon, { backgroundColor: q.color + '18' }]}><Ionicons name={q.icon as any} size={22} color={q.color} /></View>
                <Text style={s.quickTitle}>{q.title}</Text>
                <Text style={s.quickDesc}>{q.desc}</Text>
                <View style={s.quickCta}><Text style={[s.quickCtaText, { color: q.color }]}>{q.cta}</Text><Ionicons name="arrow-forward" size={14} color={q.color} /></View>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>

      <View style={[s.body, isDesktop && { maxWidth: 1200, flexDirection: 'row', gap: 40 }]}>
        <View style={[s.side, isDesktop ? { width: 260 } : { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }]}>
          {!isDesktop ? null : <Text style={s.sideTitle}>DOCUMENTATION</Text>}
          {docs.map(d => {
            const on = doc?.slug === d.slug;
            return (
              <TouchableOpacity key={d.slug} style={[s.sideItem, on && s.sideItemOn, !isDesktop && s.chip, !isDesktop && on && s.chipOn]} onPress={() => pick(d.slug)} testID={`dev-doc-${d.slug}`}>
                <Ionicons name={(ICONS[d.slug] || 'document') as any} size={16} color={on ? '#5856D6' : '#86868B'} />
                <View style={{ flex: isDesktop ? 1 : undefined }}>
                  <Text style={[s.sideLabel, on && { color: '#1D1D1F' }]}>{d.title}</Text>
                  {isDesktop && <Text style={s.sideSub}>{d.subtitle}</Text>}
                </View>
              </TouchableOpacity>
            );
          })}
          {isDesktop && doc && (
            <TouchableOpacity style={s.download} onPress={() => openUrl(doc.download_url)} testID="dev-doc-download">
              <Ionicons name="download-outline" size={15} color="#007AFF" />
              <Text style={s.downloadText}>Download as Markdown</Text>
            </TouchableOpacity>
          )}
        </View>

        <View style={s.main} testID="dev-doc-body">
          {loading && <ActivityIndicator color="#5856D6" style={{ marginTop: 40 }} />}
          {!!error && <Text style={s.error} testID="dev-doc-error">{error}</Text>}
          {doc && (
            <>
              <Text style={s.docSub}>{doc.subtitle}</Text>
              <MarkdownRenderer content={doc.content} colors={LIGHT} />
              <View style={s.helpBox}>
                <Ionicons name="chatbubble-ellipses" size={20} color="#5856D6" />
                <View style={{ flex: 1 }}>
                  <Text style={s.helpTitle}>Need a sandbox store, an organization key, or an engineer on a call?</Text>
                  <Text style={s.helpText}>Email support@imonsocial.com with your company, the system you are connecting and the dealership you are integrating for.</Text>
                </View>
              </View>
            </>
          )}
        </View>
      </View>
      <ImosFooter />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#FFF' },
  hero: { backgroundColor: '#F5F5F7', paddingVertical: 56, paddingHorizontal: 24 },
  heroInner: { alignSelf: 'center', width: '100%' },
  eyebrowRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  eyebrow: { fontSize: 12, fontWeight: '800', letterSpacing: 1.4, color: '#5856D6' },
  h1: { fontSize: 40, fontWeight: '800', color: '#1D1D1F', letterSpacing: -0.8, marginBottom: 14 },
  lead: { fontSize: 18, lineHeight: 28, color: '#515154', maxWidth: 760, marginBottom: 32 },
  quickRow: { flexDirection: 'row', gap: 16 },
  quickCard: { flex: 1, backgroundColor: '#FFF', borderRadius: 18, padding: 22, borderWidth: 1, borderColor: 'rgba(0,0,0,0.05)' },
  quickIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  quickTitle: { fontSize: 17, fontWeight: '700', color: '#1D1D1F', marginBottom: 6 },
  quickDesc: { fontSize: 14, lineHeight: 20, color: '#6E6E73', marginBottom: 14 },
  quickCta: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  quickCtaText: { fontSize: 14, fontWeight: '700' },
  body: { alignSelf: 'center', width: '100%', paddingHorizontal: 24, paddingVertical: 40 },
  side: { marginBottom: 24 },
  sideTitle: { fontSize: 11, fontWeight: '800', letterSpacing: 1.2, color: '#86868B', marginBottom: 10 },
  sideItem: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 10, paddingHorizontal: 12, borderRadius: 12 },
  sideItemOn: { backgroundColor: '#5856D610' },
  chip: { paddingVertical: 8, paddingHorizontal: 12, borderWidth: 1, borderColor: '#E5E5EA', borderRadius: 999, alignItems: 'center' },
  chipOn: { borderColor: '#5856D6', backgroundColor: '#5856D610' },
  sideLabel: { fontSize: 15, fontWeight: '600', color: '#515154' },
  sideSub: { fontSize: 12.5, color: '#86868B', marginTop: 2, lineHeight: 17 },
  download: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 12, marginTop: 8 },
  downloadText: { fontSize: 14, fontWeight: '600', color: '#007AFF' },
  main: { flex: 1, minWidth: 0 },
  docSub: { fontSize: 13, fontWeight: '700', letterSpacing: 0.8, color: '#86868B', textTransform: 'uppercase' },
  error: { color: '#FF3B30', fontSize: 15, marginTop: 20 },
  helpBox: { flexDirection: 'row', gap: 14, alignItems: 'flex-start', backgroundColor: '#5856D60D', borderRadius: 16, padding: 20, marginTop: 40 },
  helpTitle: { fontSize: 16, fontWeight: '700', color: '#1D1D1F', marginBottom: 4 },
  helpText: { fontSize: 14, lineHeight: 20, color: '#515154' },
});
