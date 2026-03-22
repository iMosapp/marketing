import React from 'react';
import { View, Text, StyleSheet, ScrollView, useWindowDimensions } from 'react-native';
import { ImosHeader, ImosFooter } from './_components';

const SECTIONS = [
  {
    title: '1. Information We Collect',
    content: `When you use i'M On Social, we collect information you provide directly, including your name, email address, phone number, profile photo, and business information. We also collect data about your contacts that you import or create within the platform, including their names, phone numbers, email addresses, and communication history.\n\nWe automatically collect usage data such as device information, IP addresses, browser type, pages visited, and feature interactions to improve our services.`,
  },
  {
    title: '2. How We Use Your Information',
    content: `We use your information to:\n\n- Provide and maintain i'M On Social services, including digital business cards, messaging, campaigns, and AI-powered features\n- Process and deliver communications you initiate through our platform\n- Generate analytics and activity reports for you and your organization\n- Improve our AI assistant (Jessi) and recommendation algorithms\n- Send you service-related notices, updates, and security alerts\n- Provide customer support`,
  },
  {
    title: '3. Contact Data You Store',
    content: `Through our CRM and relationship management features, you may store information about your contacts, including names, phone numbers, email addresses, physical addresses, dates (birthdays, anniversaries, purchase dates), vehicle information, photos, communication history, notes, and tags.\n\nThis contact data is stored securely on our servers and is accessible only to authorized users within your account or organization. We do not access, use, or share your contact data for any purpose other than providing the Service.\n\nWhen contacts are synced between our web and mobile applications, data is transmitted over encrypted connections and stored consistently across all platforms.`,
  },
  {
    title: '4. Data Storage & Security',
    content: `Your data is stored on secure, encrypted servers hosted by industry-leading cloud infrastructure providers. We implement appropriate technical and organizational measures to protect your personal data against unauthorized access, alteration, disclosure, or destruction.\n\nAll data transmitted between your device and our servers is encrypted using TLS 1.2 or higher. Database access is restricted to authorized personnel only.`,
  },
  {
    title: '5. Data Sharing & Third Parties',
    content: `We do not sell, rent, or trade your personal information to third parties. We may share data with:\n\n- Service providers who help us operate our platform (e.g., email delivery, SMS providers, cloud hosting)\n- Your organization's administrators, if you use i'M On Social as part of a team or enterprise account\n- Law enforcement or government agencies when required by applicable law\n\nAll third-party service providers are contractually obligated to protect your data.`,
  },
  {
    title: '6. Your Rights & Choices',
    content: `You have the right to:\n\n- Access, correct, or delete your personal information\n- Export your data in a portable format\n- Opt out of marketing communications\n- Request deletion of your account and associated data\n- Restrict processing of your personal data\n\nTo exercise these rights, contact us at privacy@imonsocial.com.`,
  },
  {
    title: '7. Data Transfer & Portability',
    content: `Within an organizational account, contact data may be transferred between team members by an administrator. When contacts are reassigned, the full relationship history (messages, notes, tags, activity timeline) transfers with them to ensure continuity.\n\nYou may request a full export of your data at any time. We support data portability and will provide your data in a standard format upon request.\n\nWhen a user account is deactivated within an organization, their contact data remains available to the organization. Individual (non-organizational) user data is not shared or transferred without explicit consent.`,
  },
  {
    title: '8. Data Retention',
    content: `We retain your personal data for as long as your account is active or as needed to provide services. When a user account is deactivated, we implement a soft-delete policy: account access is removed, but contact data and communication history are preserved for organizational continuity for a period of 90 days, after which they are permanently deleted unless the organization requests an extension.`,
  },
  {
    title: '9. Cookies & Tracking',
    content: `We use essential cookies to maintain your session and preferences. We use analytics tools to understand how our services are used. You can control cookie preferences through your browser settings. We do not use third-party advertising cookies.`,
  },
  {
    title: '10. Children\'s Privacy',
    content: `i'M On Social is not intended for use by individuals under the age of 16. We do not knowingly collect personal information from children. If we learn we have collected data from a child under 16, we will delete it promptly.`,
  },
  {
    title: '11. Changes to This Policy',
    content: `We may update this Privacy Policy from time to time. We will notify you of material changes by posting the updated policy on our website and updating the "Last Updated" date. Your continued use of our services after changes constitutes acceptance.`,
  },
  {
    title: '12. Contact Us',
    content: `If you have questions about this Privacy Policy or our data practices, contact us at:\n\ni'M On Social\nEmail: privacy@imonsocial.com\nGeneral: forest@imonsocial.com\nWebsite: https://imonsocial.com`,
  },
];

export default function PrivacyScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 800 : undefined;

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={[s.content, maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined]}>
          <Text style={s.label}>LEGAL</Text>
          <Text style={[s.title, isDesktop && { fontSize: 36 }]}>Privacy Policy</Text>
          <Text style={s.updated}>Last updated: March 12, 2026</Text>
          <Text style={s.intro}>
            i'M On Social ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, store, and protect your personal information when you use our Relationship Management System platform and related services.
          </Text>
          {SECTIONS.map((section, i) => (
            <View key={i} style={s.section}>
              <Text style={s.sectionTitle}>{section.title}</Text>
              <Text style={s.sectionBody}>{section.content}</Text>
            </View>
          ))}
        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingBottom: 0 },
  content: { paddingHorizontal: 20, paddingTop: 40, paddingBottom: 40 },
  label: { fontSize: 13, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', marginBottom: 8 },
  updated: { fontSize: 15, color: '#8E8E93', marginBottom: 24 },
  intro: { fontSize: 17, color: '#3A3A3C', lineHeight: 24, marginBottom: 32, borderLeftWidth: 3, borderLeftColor: '#007AFF', paddingLeft: 16 },
  section: { marginBottom: 28 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: '#1D1D1F', marginBottom: 8 },
  sectionBody: { fontSize: 17, color: '#6E6E73', lineHeight: 24 },
});
