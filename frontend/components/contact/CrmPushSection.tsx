import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, TextInput, ActivityIndicator, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

// Push a contact to any CRM as an ADF/XML lead (emailed to the CRM's intake address)
export default function CrmPushSection({ userId, contactId, contactName, colors, s }: any) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [xml, setXml] = useState('');
  const [email, setEmail] = useState('');
  const [remember, setRemember] = useState(true);
  const [copied, setCopied] = useState(false);

  const openSheet = async () => {
    setOpen(true);
    setLoading(true);
    try {
      const res = await api.get(`/crm-push/${userId}/${contactId}/preview`);
      setXml(res.data.xml || '');
      if (res.data.crm_email) setEmail(res.data.crm_email);
    } catch {}
    setLoading(false);
  };

  const send = async () => {
    if (!email.trim()) { showSimpleAlert('Missing address', "Enter your CRM's ADF intake email address."); return; }
    setSending(true);
    try {
      await api.post(`/crm-push/${userId}/${contactId}`, { email: email.trim(), save_email: remember });
      setOpen(false);
      showSimpleAlert('Lead sent', `${contactName} was pushed to your CRM as an ADF lead.`);
    } catch (e: any) {
      showSimpleAlert('Send failed', e?.response?.data?.detail || 'Could not send. Check the address and try again.');
    }
    setSending(false);
  };

  const copyXml = async () => {
    await Clipboard.setStringAsync(xml);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      <View style={s.section}>
        <TouchableOpacity
          onPress={openSheet}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: colors.border }}
          data-testid="crm-push-btn"
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#AF52DE20', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="cloud-upload" size={18} color="#AF52DE" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Push to CRM</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>Send as an ADF/XML lead to any CRM</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} activeOpacity={1} onPress={() => setOpen(false)}>
          <TouchableOpacity activeOpacity={1} onPress={() => {}}>
            <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34 }} data-testid="crm-push-sheet">
              <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: 'center', marginBottom: 16 }} />
              <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>Push to CRM</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4, lineHeight: 18 }}>
                Sends {contactName || 'this contact'} as an industry-standard ADF/XML lead. Every major CRM (VinSolutions, Elead, DriveCentric...) gives you a lead intake email address — paste it below.
              </Text>

              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, marginTop: 16, marginBottom: 6, letterSpacing: 0.4 }}>CRM INTAKE EMAIL</Text>
              <TextInput
                value={email}
                onChangeText={setEmail}
                placeholder="yourstore@lead.yourcrm.com"
                placeholderTextColor={colors.textSecondary}
                autoCapitalize="none"
                keyboardType="email-address"
                style={{ backgroundColor: colors.bg, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: colors.text }}
                data-testid="crm-email-input"
              />
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
                <Text style={{ fontSize: 13, color: colors.textSecondary }}>Remember this address</Text>
                <Switch value={remember} onValueChange={setRemember} />
              </View>

              <TouchableOpacity
                onPress={send}
                disabled={sending || loading}
                style={{ backgroundColor: sending ? colors.border : '#AF52DE', borderRadius: 16, paddingVertical: 15, alignItems: 'center', marginTop: 14, flexDirection: 'row', justifyContent: 'center', gap: 8 }}
                data-testid="crm-send-btn"
              >
                {sending ? <ActivityIndicator color="#fff" /> : <Ionicons name="cloud-upload" size={17} color="#fff" />}
                <Text style={{ fontSize: 16, fontWeight: '800', color: '#fff' }}>{sending ? 'Sending...' : 'Send Lead'}</Text>
              </TouchableOpacity>

              <TouchableOpacity
                onPress={copyXml}
                disabled={loading || !xml}
                style={{ borderRadius: 16, paddingVertical: 13, alignItems: 'center', borderWidth: 1, borderColor: colors.border, flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 10 }}
                data-testid="crm-copy-xml-btn"
              >
                <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={15} color={copied ? '#34C759' : colors.text} />
                <Text style={{ fontSize: 14, fontWeight: '700', color: copied ? '#34C759' : colors.text }}>{copied ? 'Copied!' : 'Copy ADF XML'}</Text>
              </TouchableOpacity>
              <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 8, textAlign: 'center' }}>
                Copy the XML if you'd rather paste it into your CRM manually
              </Text>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </>
  );
}
