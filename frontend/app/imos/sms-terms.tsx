import React from 'react';
import { View, Text, StyleSheet, ScrollView, useWindowDimensions, TouchableOpacity, Platform } from 'react-native';
import { ImosHeader, ImosFooter } from './_components';
import { useRouter } from 'expo-router';

const SECTIONS = [
  {
    title: '1. Overview',
    content: `I'm On Social, operated by VI Ventures Group LLC, provides SMS messaging as a feature of its Relationship Management System (RMS) platform. This policy explains how SMS messaging works within our platform, how to opt in and out, and what types of messages you may receive.`,
  },
  {
    title: '2. Who Sends Messages',
    content: `SMS messages sent through I'm On Social are sent by individual sales professionals, service advisors, and business users who have active accounts on the platform. These users send messages to their own customers and contacts who have provided consent to receive communications.\n\nI'm On Social (VI Ventures Group LLC) provides the technology platform. Message content is created and sent by the individual platform users, not by VI Ventures Group LLC directly.`,
  },
  {
    title: '3. Types of Messages',
    content: `Platform users may send the following types of messages through I'm On Social:\n\n- Relationship follow-up messages and check-ins\n- Appointment reminders and confirmations\n- Review and feedback requests\n- Digital business card and contact information sharing\n- Congratulations and milestone messages (birthdays, anniversaries, purchases)\n- Campaign-based automated follow-up sequences\n- Account notifications and updates\n- Responses to inbound customer inquiries`,
  },
  {
    title: '4. Message Frequency',
    content: `Message frequency varies based on the individual platform user's settings and the contact's relationship with that user. Messages are sent based on your opt-in consent and the communication preferences set by the user managing your relationship.\n\nYou will not receive unsolicited marketing messages. All automated messages are sent by users to their own opted-in customer contacts.`,
  },
  {
    title: '5. How to Opt In',
    content: `You may receive SMS messages from an I'm On Social user if:\n\n- You have provided your phone number to a business or sales professional who uses I'm On Social\n- You have verbally or in writing agreed to receive communications from that individual\n- You have submitted a contact form, lead form, or inquiry that includes consent language\n- You have scanned or tapped a digital business card and provided your contact information\n\nOpt-in consent is specific to the individual user or business you have a relationship with — not to I'm On Social as a platform.`,
  },
  {
    title: '6. How to Opt Out (STOP)',
    content: `You can stop receiving SMS messages at any time by replying STOP to any message you receive.\n\n- Reply STOP to unsubscribe from all messages from that sender\n- Reply HELP to receive assistance\n- Reply INFO to receive information about the service\n\nAfter opting out, you will receive one confirmation message and no further messages from that sender. Opt-out requests are processed immediately and recorded in the platform.\n\nIf you receive a message after opting out, please contact us at support@imonsocial.com.`,
  },
  {
    title: '7. Supported Carriers',
    content: `I'm On Social's SMS messaging is supported by all major U.S. wireless carriers including AT&T, T-Mobile, Verizon, and others. Carrier support may vary.\n\nMessage and data rates may apply depending on your wireless carrier plan. I'm On Social does not charge separately for SMS messages received.`,
  },
  {
    title: '8. TCPA Compliance',
    content: `I'm On Social platform users are required to comply with the Telephone Consumer Protection Act (TCPA) and all applicable federal and state communications laws when using our messaging features.\n\nPlatform users must:\n\n- Obtain proper written or verbal consent before sending automated messages\n- Honor all opt-out requests immediately\n- Not send messages to numbers on the National Do Not Call Registry unless explicit consent has been obtained\n- Not send messages to minors\n\nVI Ventures Group LLC reserves the right to suspend or terminate any user account found to be in violation of TCPA or these messaging policies.`,
  },
  {
    title: '9. A2P 10DLC',
    content: `I'm On Social uses A2P (Application-to-Person) 10DLC (10-Digit Long Code) messaging registration as required by U.S. mobile carriers. This registration ensures messages are delivered reliably and in compliance with carrier requirements.\n\nRegistered use case: Relationship follow-up, customer engagement, appointment reminders, review requests, and account notifications for opted-in users and their contacts.`,
  },
  {
    title: '10. Privacy',
    content: `Your phone number and message history are used solely for the purpose of facilitating communications between you and the I'm On Social user you have a relationship with. We do not sell phone numbers to third parties.\n\nFor full details, please review our Privacy Policy at https://imonsocial.com/privacy.`,
  },
  {
    title: '11. Contact & Support',
    content: `For questions about this SMS Messaging Policy or to report misuse:\n\nI'm On Social is operated by VI Ventures Group LLC.\nEmail: support@imonsocial.com\nWebsite: https://imonsocial.com\n\nTo opt out of messages: Reply STOP to any message you receive.\nFor help: Reply HELP to any message or email support@imonsocial.com.`,
  },
];

export default function SmsTermsScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 800 : undefined;
  const router = useRouter();

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={[s.content, maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : {}]}>
          <Text style={s.eyebrow}>Legal</Text>
          <Text style={s.title}>SMS Messaging Policy</Text>
          <Text style={s.meta}>Effective Date: January 1, 2026 · Operated by VI Ventures Group LLC</Text>

          <View style={s.stopBox}>
            <Text style={s.stopTitle}>To stop receiving messages: Reply STOP</Text>
            <Text style={s.stopSub}>For help: Reply HELP or email support@imonsocial.com</Text>
          </View>

          {SECTIONS.map((section, i) => (
            <View key={i} style={s.section}>
              <Text style={s.sectionTitle}>{section.title}</Text>
              <Text style={s.sectionContent}>{section.content}</Text>
            </View>
          ))}

          <View style={s.relatedLinks}>
            <Text style={s.relatedTitle}>Related Policies</Text>
            <TouchableOpacity onPress={() => router.push('/imos/privacy')}>
              <Text style={s.relatedLink}>Privacy Policy →</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => router.push('/imos/terms')}>
              <Text style={s.relatedLink}>Terms of Service →</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
      <ImosFooter />
    </View>
  );
}

const s = StyleSheet.create({
  container:      { flex: 1, backgroundColor: '#fff' },
  scroll:         { paddingVertical: 40, paddingHorizontal: 24 },
  content:        {},
  eyebrow:        { fontSize: 12, fontWeight: '700', color: '#007AFF', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 8 },
  title:          { fontSize: 34, fontWeight: '800', color: '#1C1C1E', marginBottom: 8, lineHeight: 40 },
  meta:           { fontSize: 14, color: '#8E8E93', marginBottom: 28 },
  stopBox:        { backgroundColor: '#34C75910', borderRadius: 12, padding: 16, marginBottom: 32, borderWidth: 1, borderColor: '#34C75930' },
  stopTitle:      { fontSize: 16, fontWeight: '700', color: '#1C7A37', marginBottom: 4 },
  stopSub:        { fontSize: 14, color: '#1C7A37' },
  section:        { marginBottom: 28 },
  sectionTitle:   { fontSize: 17, fontWeight: '700', color: '#1C1C1E', marginBottom: 8 },
  sectionContent: { fontSize: 15, color: '#3C3C43', lineHeight: 24 },
  relatedLinks:   { marginTop: 20, paddingTop: 24, borderTopWidth: 1, borderTopColor: '#F2F2F7', marginBottom: 40 },
  relatedTitle:   { fontSize: 15, fontWeight: '700', color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },
  relatedLink:    { fontSize: 16, color: '#007AFF', marginBottom: 10, fontWeight: '600' },
});
