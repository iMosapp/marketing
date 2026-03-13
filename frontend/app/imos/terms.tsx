import React from 'react';
import { View, Text, StyleSheet, ScrollView, useWindowDimensions } from 'react-native';
import { ImosHeader, ImosFooter } from './_components';

const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    content: `By accessing or using i'M On Social ("the Service"), you agree to be bound by these Terms of Service. If you do not agree to these terms, do not use the Service. These terms apply to all users, including individual users, team members, store managers, and organization administrators.`,
  },
  {
    title: '2. Description of Service',
    content: `i'M On Social provides a Relationship Management System (RMS) platform that includes digital business cards, contact management, messaging (SMS, email, and personal SMS), automated campaigns, AI-powered communication tools, analytics, and related services. The Service is available through web and mobile applications.`,
  },
  {
    title: '3. Account Registration & Security',
    content: `You must provide accurate and complete information when creating an account. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You must notify us immediately of any unauthorized use.\n\nOrganization administrators are responsible for managing user access within their organization, including adding, deactivating, and removing team members.`,
  },
  {
    title: '4. Acceptable Use',
    content: `You agree not to:\n\n- Use the Service to send unsolicited commercial messages (spam)\n- Violate any applicable laws, including CAN-SPAM, TCPA, and GDPR\n- Upload or transmit malicious code or content\n- Attempt to gain unauthorized access to the Service or other users' accounts\n- Use the Service to harass, defame, or threaten any person\n- Resell or redistribute the Service without written permission\n- Use the AI features to generate harmful, misleading, or illegal content`,
  },
  {
    title: '5. Subscription & Billing',
    content: `Paid plans are billed on a monthly or annual basis as selected at the time of purchase. Prices are subject to change with 30 days' notice. All fees are non-refundable except as required by applicable law.\n\nFree trials, if offered, automatically convert to paid subscriptions at the end of the trial period unless cancelled. You may cancel your subscription at any time through your account settings.`,
  },
  {
    title: '6. Intellectual Property',
    content: `The Service, including all software, design, text, graphics, and other content, is owned by i'M On Social and protected by intellectual property laws. You retain ownership of content you create or upload through the Service.\n\nBy using the Service, you grant us a limited, non-exclusive license to use, store, and process your content solely for the purpose of providing and improving the Service.`,
  },
  {
    title: '7. Contact Data & CRM Information',
    content: `When you use i'M On Social's Relationship Management features, you may store customer and prospect contact information including names, phone numbers, email addresses, physical addresses, birthdays, anniversaries, purchase dates, vehicle information, photos, notes, tags, and communication history.\n\nYou represent and warrant that you have obtained all necessary consents from individuals whose data you store in the platform. You are responsible for complying with all applicable data protection laws (including TCPA, CAN-SPAM, CCPA, and GDPR where applicable) when collecting, storing, and using contact data through the Service.\n\nContact data you create belongs to you. However, within an organizational account, contact data may be shared among team members within the same store or organization as configured by your administrator. When a team member's account is deactivated, their contacts remain accessible to the organization for continuity purposes.`,
  },
  {
    title: '8. Data Ownership & Portability',
    content: `You own your data. Your contacts, messages, templates, and other content created within the Service belong to you. You may export your data at any time through the platform's export features or by contacting support.\n\nWhen an organization account is terminated, data will be retained for 90 days to allow for export, after which it will be permanently deleted.\n\nContact data and communication history may be reassigned between team members within your organization by an administrator. When contacts are transferred between users, the full relationship history (messages, notes, tags, photos) transfers with them.`,
  },
  {
    title: '9. Data Transfer & Account Changes',
    content: `When team members leave an organization or change roles, administrators may reassign their contacts and related data to other team members. This ensures continuity of customer relationships.\n\nIf you are an individual user (not part of an organization), your data is private to your account and will not be shared with or transferred to any other user without your explicit consent.\n\nPartner and reseller accounts may have access to aggregated, anonymized data about accounts they manage for reporting purposes, but never direct access to individual contact records or message content.`,
  },
  {
    title: '10. SMS, Email & Communication Terms',
    content: `You agree to use the messaging features of i'M On Social in compliance with all applicable laws, including the Telephone Consumer Protection Act (TCPA), CAN-SPAM Act, and any state-level regulations.\n\nYou must obtain proper consent before sending automated messages to contacts. The platform provides tools for managing opt-outs, and you are required to honor all unsubscribe and opt-out requests promptly.\n\nMessage content sent through the platform may be stored and associated with contact records for relationship management purposes. AI-generated message suggestions are provided as drafts for your review and approval before sending.`,
  },
  {
    title: '11. API & Integration Terms',
    content: `Access to i'M On Social's public API is subject to rate limits and usage policies. API keys are confidential and must not be shared publicly. We reserve the right to revoke API access if usage policies are violated.\n\nWebhook endpoints must be secure (HTTPS) and respond within reasonable timeframes. We are not responsible for data loss due to webhook endpoint failures.`,
  },
  {
    title: '12. Limitation of Liability',
    content: `The Service is provided "as is" without warranties of any kind, express or implied. i'M On Social shall not be liable for any indirect, incidental, special, consequential, or punitive damages, including loss of profits, data, or business opportunities.\n\nOur total liability for any claim arising from or related to the Service shall not exceed the amount you paid us in the 12 months preceding the claim.`,
  },
  {
    title: '13. Termination',
    content: `We may suspend or terminate your access to the Service at any time for violation of these terms or for any other reason with reasonable notice. You may terminate your account at any time.\n\nUpon termination, your right to use the Service ceases immediately. Provisions that by their nature should survive termination will survive, including ownership, warranty disclaimers, and limitations of liability.`,
  },
  {
    title: '14. Modifications to Terms',
    content: `We reserve the right to modify these Terms at any time. Material changes will be communicated via email or in-app notification at least 30 days before they take effect. Continued use of the Service after changes take effect constitutes acceptance of the modified terms.`,
  },
  {
    title: '15. Governing Law',
    content: `These Terms shall be governed by and construed in accordance with the laws of the State of Texas, United States, without regard to conflict of law principles. Any disputes arising from these Terms shall be resolved in the courts of Texas.`,
  },
  {
    title: '16. Contact',
    content: `For questions about these Terms of Service, contact us at:\n\ni'M On Social\nEmail: legal@imonsocial.com\nGeneral: forest@imonsocial.com\nWebsite: https://imonsocial.com`,
  },
];

export default function TermsScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 800 : undefined;

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={[s.content, maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined]}>
          <Text style={s.label}>LEGAL</Text>
          <Text style={[s.title, isDesktop && { fontSize: 36 }]}>Terms of Service</Text>
          <Text style={s.updated}>Last updated: March 12, 2026</Text>
          <Text style={s.intro}>
            These Terms of Service govern your access to and use of the i'M On Social platform and services. Please read these terms carefully before using our Service.
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
  label: { fontSize: 11, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', marginBottom: 8 },
  updated: { fontSize: 13, color: '#8E8E93', marginBottom: 24 },
  intro: { fontSize: 15, color: '#3A3A3C', lineHeight: 24, marginBottom: 32, borderLeftWidth: 3, borderLeftColor: '#007AFF', paddingLeft: 16 },
  section: { marginBottom: 28 },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: '#1D1D1F', marginBottom: 8 },
  sectionBody: { fontSize: 15, color: '#6E6E73', lineHeight: 24 },
});
