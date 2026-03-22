import { useState } from 'react';
import { View, Text, ScrollView, Pressable, Image, StyleSheet, Platform } from 'react-native';
import { useRouter } from 'expo-router';

const IMAGES = {
  icloud: '/import-guide/icloud_step1.webp',
  googleMain: '/import-guide/google_step1.webp',
  googleDialog: '/import-guide/google_step2.webp',
};

function StepNumber({ n, variant }: { n: number; variant: 'apple' | 'google' }) {
  return (
    <View style={[styles.stepNum, variant === 'google' ? styles.stepNumGoogle : styles.stepNumApple]}>
      <Text style={styles.stepNumText}>{n}</Text>
    </View>
  );
}

function GuideImage({ src, compact }: { src: string; compact?: boolean }) {
  if (Platform.OS !== 'web') return null;
  return (
    <img
      src={src}
      style={{
        width: compact ? 'auto' : '100%',
        maxWidth: compact ? 360 : 700,
        borderRadius: 10,
        border: '1px solid #222',
        marginTop: 8,
        ...(compact ? { marginLeft: 44, display: 'block' } : {}),
      }}
      loading="lazy"
    />
  );
}

export default function ImportGuide() {
  const [tab, setTab] = useState<'apple' | 'google'>('apple');
  const router = useRouter();

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <Pressable onPress={() => router.back()} style={styles.backLink}>
        <Text style={styles.backText}>&larr; Back to Import</Text>
      </Pressable>

      <Text style={styles.h1}>How to Export Your Contacts</Text>
      <Text style={styles.subtitle}>Follow these steps to get your contacts file, then upload it to i'M On Social</Text>

      {/* Format cards */}
      <View style={styles.formats}>
        <View style={styles.formatCard}>
          <Text style={styles.ext}>.VCF</Text>
          <Text style={styles.formatLabel}>vCard File</Text>
          <Text style={styles.formatSource}>From Apple / iCloud</Text>
        </View>
        <View style={styles.formatCard}>
          <Text style={styles.ext}>.CSV</Text>
          <Text style={styles.formatLabel}>Spreadsheet File</Text>
          <Text style={styles.formatSource}>From Google Contacts</Text>
        </View>
      </View>

      {/* Tab bar */}
      <View style={styles.tabBar}>
        <Pressable
          style={[styles.tab, tab === 'apple' && styles.tabActive]}
          onPress={() => setTab('apple')}
          data-testid="tab-apple"
        >
          <Text style={[styles.tabText, tab === 'apple' && styles.tabTextActive]}>Apple / iCloud</Text>
        </Pressable>
        <Pressable
          style={[styles.tab, tab === 'google' && styles.tabActive]}
          onPress={() => setTab('google')}
          data-testid="tab-google"
        >
          <Text style={[styles.tabText, tab === 'google' && styles.tabTextActive]}>Google Contacts</Text>
        </Pressable>
      </View>

      {/* APPLE SECTION */}
      {tab === 'apple' && (
        <View>
          <View style={styles.step}>
            <View style={styles.stepHeader}>
              <StepNumber n={1} variant="apple" />
              <Text style={styles.stepTitle}>Open iCloud on a Computer</Text>
            </View>
            <Text style={styles.stepDesc}>
              On a computer (not your phone), open a web browser and go to <Text style={styles.bold}>icloud.com</Text>. Sign in with your Apple ID and password, then click the <Text style={styles.bold}>Contacts</Text> app icon.
            </Text>
          </View>

          <View style={styles.step}>
            <View style={styles.stepHeader}>
              <StepNumber n={2} variant="apple" />
              <Text style={styles.stepTitle}>Select All, then Export</Text>
            </View>
            <Text style={styles.stepDesc}>
              Once you're in iCloud Contacts, click the <Text style={styles.bold}>settings icon</Text> (gear) at the top left, then click <Text style={styles.bold}>"Select All Contacts"</Text>. Once all contacts are highlighted, click the <Text style={styles.bold}>share icon</Text> (box with arrow) at the top right and choose <Text style={styles.bold}>"Export vCard"</Text>. A <Text style={styles.bold}>.vcf</Text> file will download to your computer.
            </Text>
            <GuideImage src={IMAGES.icloud} />
          </View>

          <View style={styles.step}>
            <View style={styles.stepHeader}>
              <StepNumber n={3} variant="apple" />
              <Text style={styles.stepTitle}>Upload to i'M On Social</Text>
            </View>
            <Text style={styles.stepDesc}>
              Go back to the Import Contacts screen in i'M On Social, tap <Text style={styles.bold}>"From File (CSV or VCF)"</Text>, and select the .vcf file you just downloaded. You'll see a preview of all your contacts before importing.
            </Text>
          </View>

          <View style={styles.callout}>
            <Text style={styles.calloutText}>
              <Text style={styles.calloutBold}>Tip:</Text> Your contacts will be imported as personal contacts, meaning they stay with you even if you move to a different organization.
            </Text>
          </View>
        </View>
      )}

      {/* GOOGLE SECTION */}
      {tab === 'google' && (
        <View>
          <View style={styles.step}>
            <View style={styles.stepHeader}>
              <StepNumber n={1} variant="google" />
              <Text style={styles.stepTitle}>Go to Google Contacts</Text>
            </View>
            <Text style={styles.stepDesc}>
              On a computer, open your browser and go to <Text style={styles.bold}>contacts.google.com</Text>. Sign in with your Google account if you're not already logged in.
            </Text>
          </View>

          <View style={styles.step}>
            <View style={styles.stepHeader}>
              <StepNumber n={2} variant="google" />
              <Text style={styles.stepTitle}>Click the Export Button</Text>
            </View>
            <Text style={styles.stepDesc}>
              Look for the <Text style={styles.bold}>"Export"</Text> button in the <Text style={styles.bold}>top-right area</Text> of your contacts list (next to the print icon). Click it.
            </Text>
            <GuideImage src={IMAGES.googleMain} />
          </View>

          <View style={styles.step}>
            <View style={styles.stepHeader}>
              <StepNumber n={3} variant="google" />
              <Text style={styles.stepTitle}>Choose your format and export</Text>
            </View>
            <Text style={styles.stepDesc}>
              In the Export dialog, make sure <Text style={styles.bold}>"Contacts"</Text> is selected at the top. Then choose either:{'\n\n'}<Text style={styles.bold}>"Google CSV"</Text> for a spreadsheet file, or{'\n'}<Text style={styles.bold}>"vCard (for Android or iOS)"</Text> for a vCard file.{'\n\n'}Either format works. Click <Text style={styles.bold}>"Export"</Text> and the file will download.
            </Text>
            <GuideImage src={IMAGES.googleDialog} compact />
          </View>

          <View style={styles.step}>
            <View style={styles.stepHeader}>
              <StepNumber n={4} variant="google" />
              <Text style={styles.stepTitle}>Upload to i'M On Social</Text>
            </View>
            <Text style={styles.stepDesc}>
              Go back to the Import Contacts screen in i'M On Social, tap <Text style={styles.bold}>"From File (CSV or VCF)"</Text>, and select the file you just downloaded. You'll see a preview of all your contacts before importing.
            </Text>
          </View>

          <View style={styles.callout}>
            <Text style={styles.calloutText}>
              <Text style={styles.calloutBold}>Tip:</Text> Your contacts will be imported as personal contacts, meaning they stay with you even if you move to a different organization.
            </Text>
          </View>

          <View style={styles.calloutWarn}>
            <Text style={styles.calloutWarnText}>
              <Text style={styles.calloutWarnBold}>Note:</Text> We'll automatically detect and match names, phone numbers, email addresses, birthdays, organizations, and addresses. Any duplicates will be flagged so you can choose whether to import them.
            </Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0a0a0a' },
  container: { maxWidth: 800, alignSelf: 'center', width: '100%', padding: 20, paddingBottom: 60 },
  backLink: { marginBottom: 20 },
  backText: { color: '#007AFF', fontSize: 17 },
  h1: { fontSize: 28, fontWeight: '700', textAlign: 'center', color: '#f5f5f5', marginBottom: 8 },
  subtitle: { textAlign: 'center', color: '#888', fontSize: 17, marginBottom: 40 },
  formats: { flexDirection: 'row', gap: 12, marginBottom: 20 },
  formatCard: { flex: 1, backgroundColor: '#1a1a1a', borderRadius: 10, padding: 16, alignItems: 'center', borderWidth: 1, borderColor: '#222' },
  ext: { fontSize: 24, fontWeight: '700', color: '#007AFF' },
  formatLabel: { fontSize: 14, color: '#888', marginTop: 4 },
  formatSource: { fontSize: 15, color: '#aaa', marginTop: 8 },
  tabBar: { flexDirection: 'row', backgroundColor: '#1a1a1a', borderRadius: 12, padding: 4, marginBottom: 32 },
  tab: { flex: 1, alignItems: 'center', padding: 12, borderRadius: 10 },
  tabActive: { backgroundColor: '#222' },
  tabText: { fontSize: 17, fontWeight: '600', color: '#888' },
  tabTextActive: { color: '#fff' },
  step: { marginBottom: 32 },
  stepHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 12 },
  stepNum: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  stepNumApple: { backgroundColor: '#333' },
  stepNumGoogle: { backgroundColor: '#4285f4' },
  stepNumText: { color: '#fff', fontWeight: '700', fontSize: 17 },
  stepTitle: { fontSize: 18, fontWeight: '600', color: '#f5f5f5' },
  stepDesc: { color: '#aaa', fontSize: 16, lineHeight: 22, paddingLeft: 44 },
  bold: { fontWeight: '700', color: '#ddd' },
  callout: { backgroundColor: '#1a2a1a', borderWidth: 1, borderColor: '#2a4a2a', borderRadius: 10, padding: 14, marginTop: 24 },
  calloutText: { fontSize: 16, color: '#8fbc8f', lineHeight: 20 },
  calloutBold: { fontWeight: '700', color: '#a5d6a5' },
  calloutWarn: { backgroundColor: '#2a2a1a', borderWidth: 1, borderColor: '#4a4a2a', borderRadius: 10, padding: 14, marginTop: 16 },
  calloutWarnText: { fontSize: 16, color: '#bcbc8f', lineHeight: 20 },
  calloutWarnBold: { fontWeight: '700', color: '#d6d6a5' },
});
