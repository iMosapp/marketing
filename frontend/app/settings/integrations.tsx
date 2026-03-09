import React, {
  useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { WebModal } from '../../components/WebModal';
import { useToast } from '../../components/common/Toast';

import { useThemeStore } from '../../store/themeStore';
type TabType = 'api-keys' | 'webhooks' | 'crm' | 'dms' | 'docs';

interface Provider {
  name: string;
  type: string;
  description: string;
  auth_type: string;
  docs_url?: string;
  required_fields?: string[];
}

export default function IntegrationsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
const { showToast } = useToast();
    const [activeTab, setActiveTab] = useState<TabType>('api-keys');
  const [loading, setLoading] = useState(true);
  
  // API Keys
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [showNewKeyModal, setShowNewKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  
  // Webhooks
  const [webhooks, setWebhooks] = useState<any[]>([]);
  const [webhookEvents, setWebhookEvents] = useState<Record<string, string>>({});
  const [showNewWebhookModal, setShowNewWebhookModal] = useState(false);
  const [newWebhook, setNewWebhook] = useState({ name: '', url: '', events: [] as string[] });
  
  // Providers
  const [providers, setProviders] = useState<{ crm: Record<string, Provider>; dms: Record<string, Provider> }>({ crm: {}, dms: {} });
  const [connections, setConnections] = useState<any[]>([]);
  
  // CRM Timeline PIN Settings
  const [crmPinEnabled, setCrmPinEnabled] = useState(false);
  const [crmPin, setCrmPin] = useState('');
  const [savingPin, setSavingPin] = useState(false);
  
  const [docsSection, setDocsSection] = useState('getting-started');

  const APP_URL = 'https://app.imonsocial.com';

  const API_REFERENCE = {
    contacts: {
      title: 'Contacts',
      icon: 'people',
      color: '#007AFF',
      endpoints: [
        { method: 'GET', path: '/api/v1/contacts', desc: 'List all contacts', params: 'search, tag, source, ownership_type, limit, offset' },
        { method: 'GET', path: '/api/v1/contacts/:id', desc: 'Get contact details' },
        { method: 'POST', path: '/api/v1/contacts', desc: 'Create a contact', body: '{ first_name, last_name, phone, email, tags[], source, external_id }' },
        { method: 'PUT', path: '/api/v1/contacts/:id', desc: 'Update a contact', body: '{ any contact fields }' },
        { method: 'DELETE', path: '/api/v1/contacts/:id', desc: 'Soft-delete a contact' },
        { method: 'POST', path: '/api/v1/contacts/:id/tags', desc: 'Add tag to contact', body: '{ tag: "VIP" }' },
        { method: 'DELETE', path: '/api/v1/contacts/:id/tags/:tag', desc: 'Remove tag from contact' },
        { method: 'POST', path: '/api/v1/contacts/:id/notes', desc: 'Add note to contact', body: '{ note: "..." }' },
        { method: 'GET', path: '/api/v1/contacts/:id/events', desc: 'Get activity timeline' },
        { method: 'POST', path: '/api/v1/contacts/:id/events', desc: 'Log custom event', body: '{ event_type, description, metadata }' },
        { method: 'POST', path: '/api/v1/contacts/bulk-tag', desc: 'Tag multiple contacts', body: '{ contact_ids[], tag }' },
        { method: 'POST', path: '/api/v1/contacts/bulk-assign', desc: 'Reassign contacts', body: '{ contact_ids[], user_id }' },
        { method: 'GET', path: '/api/v1/export/contacts', desc: 'Export all contacts (JSON)' },
      ],
    },
    users: {
      title: 'Users',
      icon: 'person',
      color: '#5856D6',
      endpoints: [
        { method: 'GET', path: '/api/v1/users', desc: 'List all users', params: 'role, status, limit, offset' },
        { method: 'GET', path: '/api/v1/users/:id', desc: 'Get user details' },
        { method: 'GET', path: '/api/v1/users/:id/contacts', desc: 'Get user\'s contacts' },
        { method: 'GET', path: '/api/v1/users/:id/stats', desc: 'Get user activity stats' },
      ],
    },
    messages: {
      title: 'Messages',
      icon: 'chatbubbles',
      color: '#34C759',
      endpoints: [
        { method: 'GET', path: '/api/v1/conversations', desc: 'List conversations', params: 'user_id, status, limit, offset' },
        { method: 'GET', path: '/api/v1/conversations/:id/messages', desc: 'Get messages in conversation' },
        { method: 'POST', path: '/api/v1/messages', desc: 'Send a message', body: '{ to, content, user_id, mode: "sms"|"email" }' },
      ],
    },
    campaigns: {
      title: 'Campaigns',
      icon: 'rocket',
      color: '#FF9500',
      endpoints: [
        { method: 'GET', path: '/api/v1/campaigns', desc: 'List campaigns' },
        { method: 'GET', path: '/api/v1/campaigns/:id', desc: 'Get campaign with stats' },
        { method: 'GET', path: '/api/v1/campaigns/:id/enrollments', desc: 'Get enrollments' },
      ],
    },
    reviews: {
      title: 'Reviews',
      icon: 'star',
      color: '#FFD60A',
      endpoints: [
        { method: 'GET', path: '/api/v1/reviews', desc: 'List reviews', params: 'status, store_id, limit, offset' },
      ],
    },
    orgs: {
      title: 'Organizations & Stores',
      icon: 'business',
      color: '#AF52DE',
      endpoints: [
        { method: 'GET', path: '/api/v1/organizations', desc: 'List organizations' },
        { method: 'GET', path: '/api/v1/stores', desc: 'List stores' },
        { method: 'GET', path: '/api/v1/tags', desc: 'List all tags' },
      ],
    },
    keys: {
      title: 'API Key Management',
      icon: 'key',
      color: '#FF2D55',
      endpoints: [
        { method: 'POST', path: '/api/v1/api-keys', desc: 'Generate new API key', body: '{ name, scope: "full"|"read_only" }' },
        { method: 'GET', path: '/api/v1/api-keys', desc: 'List API keys' },
        { method: 'DELETE', path: '/api/v1/api-keys/:id', desc: 'Revoke an API key' },
      ],
    },
  };

  const WEBHOOK_EVENTS = [
    { event: 'contact.created', desc: 'New contact added', payload: '{ contact_id, first_name, last_name, phone, email, tags, source }' },
    { event: 'contact.updated', desc: 'Contact info changed', payload: '{ contact_id, changes: { field: new_value } }' },
    { event: 'contact.deleted', desc: 'Contact removed', payload: '{ contact_id }' },
    { event: 'contact.tagged', desc: 'Tag added/removed', payload: '{ contact_id, tag, action }' },
    { event: 'message.sent', desc: 'Message sent to contact', payload: '{ message_id, to, content, mode }' },
    { event: 'message.received', desc: 'Incoming message from contact', payload: '{ message_id, from, content }' },
    { event: 'campaign.enrolled', desc: 'Contact enrolled in campaign', payload: '{ contact_id, campaign_id }' },
    { event: 'campaign.completed', desc: 'Campaign finished for contact', payload: '{ contact_id, campaign_id }' },
    { event: 'campaign.step_sent', desc: 'Campaign step delivered', payload: '{ contact_id, campaign_id, step }' },
    { event: 'review.submitted', desc: 'Customer submitted a review', payload: '{ review_id, store_id, rating, content }' },
    { event: 'review.approved', desc: 'Review approved by manager', payload: '{ review_id }' },
    { event: 'congrats.sent', desc: 'Congrats card sent', payload: '{ card_id, contact_id }' },
    { event: 'user.created', desc: 'New user account created', payload: '{ user_id, name, role }' },
    { event: 'user.deactivated', desc: 'User account deactivated', payload: '{ user_id, deactivated_by }' },
    { event: 'user.reactivated', desc: 'User account restored', payload: '{ user_id }' },
    { event: 'deal.closed', desc: 'Deal/sale completed', payload: '{ contact_id, deal_id, amount }' },
    { event: 'call.logged', desc: 'Phone call recorded', payload: '{ contact_id, duration }' },
    { event: 'note.added', desc: 'Note added to contact', payload: '{ contact_id }' },
    { event: 'tag.added', desc: 'Tag applied to contact', payload: '{ contact_id, tag }' },
    { event: 'tag.removed', desc: 'Tag removed from contact', payload: '{ contact_id, tag }' },
    { event: 'appointment.created', desc: 'Appointment scheduled', payload: '{ contact_id, date }' },
  ];

  useEffect(() => {
    if (user?.store_id) {
      loadData();
    } else if (user?._id) {
      // User loaded but no store_id - stop loading spinner
      setLoading(false);
    }
  }, [user?.store_id, user?._id]);

  const loadData = async () => {
    if (!user?.store_id) return;
    
    setLoading(true);
    try {
      const [keysRes, webhooksRes, eventsRes, providersRes, connectionsRes] = await Promise.all([
        api.get(`/integrations/api-keys?store_id=${user.store_id}`),
        api.get(`/integrations/webhooks?store_id=${user.store_id}`),
        api.get('/integrations/webhooks/events'),
        api.get('/integrations/providers'),
        api.get(`/integrations/connections?store_id=${user.store_id}`),
      ]);
      
      setApiKeys(keysRes.data);
      setWebhooks(webhooksRes.data);
      setWebhookEvents(eventsRes.data);
      setProviders(providersRes.data);
      setConnections(connectionsRes.data);
      
      // Load CRM PIN settings
      try {
        const pinRes = await api.get(`/crm/pin-settings/${user.store_id}`);
        setCrmPinEnabled(pinRes.data?.crm_pin_enabled ?? false);
        setCrmPin(pinRes.data?.crm_pin ?? '');
      } catch {}
    } catch (error) {
      console.error('Error loading integrations:', error);
    } finally {
      setLoading(false);
    }
  };

  const createApiKey = async () => {
    if (!newKeyName.trim() || !user?.store_id) return;
    
    setCreatingKey(true);
    try {
      const response = await api.post(`/integrations/api-keys?store_id=${user.store_id}`, {
        name: newKeyName,
        scopes: ['read', 'write'],
      });
      
      setNewlyCreatedKey(response.data.key);
      setApiKeys(prev => [...prev, response.data]);
      setNewKeyName('');
    } catch (error) {
      Alert.alert('Error', 'Failed to create API key');
    } finally {
      setCreatingKey(false);
    }
  };

  const revokeApiKey = async (keyId: string) => {
    Alert.alert(
      'Revoke API Key',
      'Are you sure? This cannot be undone and any integrations using this key will stop working.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Revoke',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/integrations/api-keys/${keyId}`);
              setApiKeys(prev => prev.filter(k => k.id !== keyId));
            } catch (error) {
              Alert.alert('Error', 'Failed to revoke API key');
            }
          },
        },
      ]
    );
  };

  const createWebhook = async () => {
    if (!newWebhook.name.trim() || !newWebhook.url.trim() || !user?.store_id) return;
    
    try {
      const response = await api.post(`/integrations/webhooks?store_id=${user.store_id}`, newWebhook);
      setWebhooks(prev => [...prev, response.data]);
      setShowNewWebhookModal(false);
      setNewWebhook({ name: '', url: '', events: [] });
      showToast('Webhook created');
    } catch (error) {
      Alert.alert('Error', 'Failed to create webhook');
    }
  };

  const testWebhook = async (webhookId: string) => {
    try {
      const response = await api.post(`/integrations/webhooks/${webhookId}/test`);
      Alert.alert(
        response.data.success ? 'Success' : 'Failed',
        response.data.success 
          ? `Webhook responded with status ${response.data.status_code}`
          : response.data.error || 'Webhook test failed'
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to test webhook');
    }
  };

  const copyToClipboard = async (text: string) => {
    await Clipboard.setStringAsync(text);
    showToast('Copied to clipboard');
  };

  const renderApiKeysTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.sectionHeader}>
        <View>
          <Text style={styles.sectionTitle}>API Keys</Text>
          <Text style={styles.sectionSubtitle}>
            Manage keys for external integrations
          </Text>
        </View>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => setShowNewKeyModal(true)}
        >
          <Ionicons name="add" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>
      
      {apiKeys.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="key-outline" size={48} color={colors.textSecondary} />
          <Text style={styles.emptyText}>No API keys yet</Text>
          <Text style={styles.emptySubtext}>Create a key to integrate with external systems</Text>
        </View>
      ) : (
        apiKeys.map((key) => (
          <View key={key.id} style={styles.keyCard}>
            <View style={styles.keyHeader}>
              <Text style={styles.keyName}>{key.name}</Text>
              <View style={[styles.statusBadge, key.active ? styles.activeBadge : styles.revokedBadge]}>
                <Text style={styles.statusText}>{key.active ? 'Active' : 'Revoked'}</Text>
              </View>
            </View>
            <Text style={styles.keyPrefix}>Key: {key.key_prefix}...</Text>
            <Text style={styles.keyMeta}>
              Created: {new Date(key.created_at).toLocaleDateString()}
              {key.last_used_at && ` • Last used: ${new Date(key.last_used_at).toLocaleDateString()}`}
            </Text>
            <View style={styles.keyActions}>
              <Text style={styles.keyRequests}>{key.request_count} requests</Text>
              {key.active && (
                <TouchableOpacity onPress={() => revokeApiKey(key.id)}>
                  <Text style={styles.revokeButton}>Revoke</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        ))
      )}
    </View>
  );

  const renderWebhooksTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.sectionHeader}>
        <View>
          <Text style={styles.sectionTitle}>Webhooks</Text>
          <Text style={styles.sectionSubtitle}>
            Receive real-time notifications
          </Text>
        </View>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => setShowNewWebhookModal(true)}
        >
          <Ionicons name="add" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>
      
      {webhooks.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="git-branch-outline" size={48} color={colors.textSecondary} />
          <Text style={styles.emptyText}>No webhooks configured</Text>
          <Text style={styles.emptySubtext}>Set up webhooks to sync data with Zapier, Make, or your own systems</Text>
        </View>
      ) : (
        webhooks.map((webhook) => (
          <View key={webhook.id} style={styles.webhookCard}>
            <View style={styles.webhookHeader}>
              <Text style={styles.webhookName}>{webhook.name}</Text>
              <View style={[styles.statusBadge, webhook.active ? styles.activeBadge : styles.revokedBadge]}>
                <Text style={styles.statusText}>{webhook.active ? 'Active' : 'Inactive'}</Text>
              </View>
            </View>
            <Text style={styles.webhookUrl} numberOfLines={1}>{webhook.url}</Text>
            <View style={styles.webhookEvents}>
              {webhook.events.slice(0, 3).map((event: string) => (
                <View key={event} style={styles.eventChip}>
                  <Text style={styles.eventChipText}>{event}</Text>
                </View>
              ))}
              {webhook.events.length > 3 && (
                <Text style={styles.moreEvents}>+{webhook.events.length - 3} more</Text>
              )}
            </View>
            <View style={styles.webhookActions}>
              <Text style={styles.webhookStats}>
                {webhook.delivery_count} sent • {webhook.failure_count} failed
              </Text>
              <TouchableOpacity onPress={() => testWebhook(webhook.id)}>
                <Text style={styles.testButton}>Test</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))
      )}
    </View>
  );


  const renderCrmTimelineSettings = () => (
    <View style={styles.tabContent}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Text style={styles.sectionTitle}>CRM Timeline Export</Text>
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#C9A96220', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 }}
          onPress={() => router.push('/admin/crm-dashboard' as any)}
          data-testid="crm-dashboard-link"
        >
          <Ionicons name="stats-chart" size={14} color="#C9A962" />
          <Text style={{ color: '#C9A962', fontSize: 13, fontWeight: '700' }}>Dashboard</Text>
        </TouchableOpacity>
      </View>
      <Text style={styles.sectionSubtitle}>
        Generate live activity links for each contact that can be pasted into any CRM
      </Text>

      <View style={[styles.connectionCard, { marginTop: 16 }]}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.connectionName, { fontSize: 15 }]}>PIN Protection</Text>
            <Text style={[styles.sectionSubtitle, { marginTop: 2, marginBottom: 0 }]}>
              Require a store PIN to view timeline links
            </Text>
          </View>
          <TouchableOpacity
            style={{
              width: 52, height: 30, borderRadius: 15,
              backgroundColor: crmPinEnabled ? '#34C759' : '#3A3A3C',
              justifyContent: 'center',
              paddingHorizontal: 2,
            }}
            onPress={async () => {
              const newVal = !crmPinEnabled;
              setCrmPinEnabled(newVal);
              if (!user?.store_id) return;
              try {
                const payload: any = { crm_pin_enabled: newVal };
                if (newVal && !crmPin) {
                  const autoPin = String(Math.floor(1000 + Math.random() * 9000));
                  setCrmPin(autoPin);
                  payload.crm_pin = autoPin;
                }
                await api.put(`/crm/pin-settings/${user.store_id}`, payload);
                showToast(newVal ? 'PIN protection enabled' : 'PIN protection disabled', 'success');
              } catch {
                setCrmPinEnabled(!newVal);
              }
            }}
            data-testid="crm-pin-toggle"
          >
            <View style={{
              width: 26, height: 26, borderRadius: 13, backgroundColor: '#FFF',
              transform: [{ translateX: crmPinEnabled ? 22 : 0 }],
            }} />
          </TouchableOpacity>
        </View>

        {crmPinEnabled && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4 }}>
            <TextInput
              style={[styles.input, { flex: 1, letterSpacing: 4, fontSize: 18, textAlign: 'center' }]}
              value={crmPin}
              onChangeText={(t: string) => setCrmPin(t.replace(/\D/g, '').slice(0, 8))}
              placeholder="4-8 digit PIN"
              placeholderTextColor="#666"
              keyboardType="number-pad"
              maxLength={8}
              data-testid="crm-pin-input-settings"
            />
            <TouchableOpacity
              style={{
                backgroundColor: '#C9A962', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 8,
                opacity: savingPin ? 0.5 : 1,
              }}
              onPress={async () => {
                if (!user?.store_id || !crmPin || crmPin.length < 4) {
                  showToast('PIN must be 4-8 digits', 'error');
                  return;
                }
                setSavingPin(true);
                try {
                  await api.put(`/crm/pin-settings/${user.store_id}`, { crm_pin: crmPin, crm_pin_enabled: true });
                  showToast('PIN saved', 'success');
                } catch {
                  showToast('Failed to save PIN', 'error');
                } finally {
                  setSavingPin(false);
                }
              }}
              disabled={savingPin}
              data-testid="crm-pin-save"
            >
              <Text style={{ color: '#000', fontWeight: '700', fontSize: 14 }}>
                {savingPin ? 'Saving...' : 'Save'}
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <View style={[styles.connectionCard, { marginTop: 12, backgroundColor: '#1C1C1E' }]}>
        <Ionicons name="information-circle-outline" size={20} color="#C9A962" style={{ marginBottom: 8 }} />
        <Text style={[styles.sectionSubtitle, { marginBottom: 0 }]}>
          Each contact gets a unique link you can copy from their profile under "Share Your Stuff". 
          Paste it into your CRM and it stays up-to-date automatically. Use the Contacts tab to filter 
          which contacts have been linked vs. not yet.
        </Text>
      </View>
    </View>
  );

  const renderProvidersTab = (type: 'crm' | 'dms') => {
    const providerList = type === 'crm' ? providers.crm : providers.dms;
    const typeConnections = connections.filter(c => c.provider_type === type);
    
    return (
      <View style={styles.tabContent}>
        <Text style={styles.sectionTitle}>{type === 'crm' ? 'RMS Integrations' : 'DMS Integrations'}</Text>
        <Text style={styles.sectionSubtitle}>
          {type === 'crm' 
            ? 'Sync contacts and deals with your RMS' 
            : 'Connect to dealer management systems'}
        </Text>
        
        {/* Connected */}
        {typeConnections.length > 0 && (
          <View style={styles.connectedSection}>
            <Text style={styles.subsectionTitle}>Connected</Text>
            {typeConnections.map((conn) => (
              <View key={conn.id} style={styles.connectionCard}>
                <View style={styles.connectionHeader}>
                  <Text style={styles.connectionName}>{conn.provider_name}</Text>
                  <View style={[
                    styles.syncBadge,
                    conn.sync_status === 'success' ? styles.syncSuccess : 
                    conn.sync_status === 'error' ? styles.syncError : styles.syncPending
                  ]}>
                    <Text style={styles.syncText}>{conn.sync_status}</Text>
                  </View>
                </View>
                {conn.last_sync_at && (
                  <Text style={styles.lastSync}>
                    Last sync: {new Date(conn.last_sync_at).toLocaleString()}
                  </Text>
                )}
              </View>
            ))}
          </View>
        )}
        
        {/* Available */}
        <View style={styles.availableSection}>
          <Text style={styles.subsectionTitle}>Available Integrations</Text>
          {Object.entries(providerList).map(([key, provider]) => (
            <TouchableOpacity
              key={key}
              style={styles.providerCard}
              onPress={() => Linking.openURL(provider.docs_url || '#')}
            >
              <View style={styles.providerInfo}>
                <Text style={styles.providerName}>{provider.name}</Text>
                <Text style={styles.providerDesc}>{provider.description}</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          ))}
        </View>
      </View>
    );
  };

  const METHOD_COLORS: Record<string, string> = {
    GET: '#34C759', POST: '#007AFF', PUT: '#FF9500', DELETE: '#FF3B30',
  };

  const renderDocsTab = () => (
    <View style={styles.tabContent}>
      {/* Quick Nav */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {[
            { key: 'getting-started', label: 'Start' },
            { key: 'endpoints', label: 'Endpoints' },
            { key: 'webhooks-ref', label: 'Webhooks' },
            { key: 'examples', label: 'Examples' },
            { key: 'zapier', label: 'Zapier' },
          ].map(s => (
            <TouchableOpacity
              key={s.key}
              style={[styles.docNavPill, docsSection === s.key && styles.docNavPillActive]}
              onPress={() => setDocsSection(s.key)}
            >
              <Text style={[styles.docNavText, docsSection === s.key && styles.docNavTextActive]}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Getting Started */}
      {docsSection === 'getting-started' && (
        <>
          <Text style={styles.docSectionTitle}>Getting Started</Text>
          <Text style={styles.docParagraph}>
            The i'M On Social API lets you manage contacts, send messages, run campaigns, and sync data with any external system.
          </Text>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Base URL</Text>
            <TouchableOpacity style={styles.codeBlock} onPress={() => copyToClipboard(`${APP_URL}/api/v1`)}>
              <Text style={styles.codeText}>{APP_URL}/api/v1</Text>
              <Ionicons name="copy-outline" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Authentication</Text>
            <Text style={styles.docParagraph}>
              All API requests require an API key passed in the header:
            </Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeComment}>// Include with every request</Text>
              <Text style={styles.codeText}>X-API-Key: imos_your_key_here</Text>
            </View>
            <Text style={[styles.docParagraph, { marginTop: 8 }]}>
              Generate keys from the API Keys tab. Keys can be scoped to full access or read-only.
            </Text>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Rate Limits</Text>
            <Text style={styles.docParagraph}>60 requests/minute, 10,000 requests/day per key.</Text>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Response Format</Text>
            <Text style={styles.docParagraph}>All responses are JSON. List endpoints return:</Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeText}>{'{'}</Text>
              <Text style={styles.codeText}>  "contacts": [...],</Text>
              <Text style={styles.codeText}>  "total": 150,</Text>
              <Text style={styles.codeText}>  "limit": 50,</Text>
              <Text style={styles.codeText}>  "offset": 0</Text>
              <Text style={styles.codeText}>{'}'}</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>3rd Party CRM IDs</Text>
            <Text style={styles.docParagraph}>
              Contacts and Users support external system IDs for syncing:
            </Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeComment}>// Map your system IDs</Text>
              <Text style={styles.codeText}>{'{'}</Text>
              <Text style={styles.codeText}>  "external_id": "SF-12345",</Text>
              <Text style={styles.codeText}>  "external_ids": {'{'}</Text>
              <Text style={styles.codeText}>    "salesforce": "SF-12345",</Text>
              <Text style={styles.codeText}>    "cdk": "CDK-789",</Text>
              <Text style={styles.codeText}>    "vin_solutions": "VS-456"</Text>
              <Text style={styles.codeText}>  {'}'},</Text>
              <Text style={styles.codeText}>  "dms_id": "DMS-001",</Text>
              <Text style={styles.codeText}>  "crm_id": "CRM-002",</Text>
              <Text style={styles.codeText}>  "customer_number": "CUST-9876"</Text>
              <Text style={styles.codeText}>{'}'}</Text>
            </View>
          </View>
        </>
      )}

      {/* Endpoints */}
      {docsSection === 'endpoints' && (
        <>
          <Text style={styles.docSectionTitle}>API Endpoints</Text>
          {Object.entries(API_REFERENCE).map(([key, section]) => (
            <View key={key} style={styles.docCard}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <View style={[styles.docIconBadge, { backgroundColor: `${section.color}20` }]}>
                  <Ionicons name={section.icon as any} size={16} color={section.color} />
                </View>
                <Text style={styles.docCardTitle}>{section.title}</Text>
              </View>
              {section.endpoints.map((ep, i) => (
                <TouchableOpacity key={i} style={styles.endpointRow} onPress={() => copyToClipboard(`${APP_URL}${ep.path}`)}>
                  <View style={[styles.methodTag, { backgroundColor: `${METHOD_COLORS[ep.method]}20` }]}>
                    <Text style={[styles.methodTagText, { color: METHOD_COLORS[ep.method] }]}>{ep.method}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.endpointPathText}>{ep.path}</Text>
                    <Text style={styles.endpointDescText}>{ep.desc}</Text>
                    {ep.params && <Text style={styles.endpointParams}>Params: {ep.params}</Text>}
                    {ep.body && <Text style={styles.endpointBody}>Body: {ep.body}</Text>}
                  </View>
                </TouchableOpacity>
              ))}
            </View>
          ))}
        </>
      )}

      {/* Webhooks Reference */}
      {docsSection === 'webhooks-ref' && (
        <>
          <Text style={styles.docSectionTitle}>Webhook Events</Text>
          <Text style={styles.docParagraph}>
            Register webhook URLs to receive real-time notifications when events happen in i'M On Social. 
            All payloads include an event name, timestamp, and data object.
          </Text>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Payload Format</Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeText}>{'{'}</Text>
              <Text style={styles.codeText}>  "event": "contact.created",</Text>
              <Text style={styles.codeText}>  "timestamp": "2026-02-27T...",</Text>
              <Text style={styles.codeText}>  "data": {'{ ... }'}</Text>
              <Text style={styles.codeText}>{'}'}</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Security</Text>
            <Text style={styles.docParagraph}>
              Set a shared secret when creating a webhook. i'M On Social signs each payload with HMAC-SHA256 in the{' '}
              <Text style={styles.codeInline}>X-IMOS-Signature</Text> header.
            </Text>
          </View>

          <Text style={[styles.docSectionTitle, { fontSize: 16, marginTop: 16 }]}>All Events ({WEBHOOK_EVENTS.length})</Text>
          {WEBHOOK_EVENTS.map((evt, i) => (
            <View key={i} style={styles.webhookEventRow}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <View style={[styles.eventDot, { backgroundColor: evt.event.startsWith('contact') ? '#007AFF' : evt.event.startsWith('message') ? '#34C759' : evt.event.startsWith('campaign') ? '#FF9500' : evt.event.startsWith('review') ? '#FFD60A' : evt.event.startsWith('user') ? '#5856D6' : colors.textSecondary }]} />
                <Text style={styles.webhookEventName}>{evt.event}</Text>
              </View>
              <Text style={styles.webhookEventDesc}>{evt.desc}</Text>
              <Text style={styles.webhookEventPayload}>Payload: {evt.payload}</Text>
            </View>
          ))}
        </>
      )}

      {/* Code Examples */}
      {docsSection === 'examples' && (
        <>
          <Text style={styles.docSectionTitle}>Code Examples</Text>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>cURL  - List Contacts</Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeText}>curl -X GET \</Text>
              <Text style={styles.codeText}>  "{APP_URL}/api/v1/contacts?limit=10" \</Text>
              <Text style={styles.codeText}>  -H "X-API-Key: imos_your_key"</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>cURL  - Create Contact</Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeText}>curl -X POST \</Text>
              <Text style={styles.codeText}>  "{APP_URL}/api/v1/contacts" \</Text>
              <Text style={styles.codeText}>  -H "X-API-Key: imos_your_key" \</Text>
              <Text style={styles.codeText}>  -H "Content-Type: application/json" \</Text>
              <Text style={styles.codeText}>  -d '{'"first_name":"John","last_name":"Doe","phone":"+15551234567","tags":["VIP"],"external_id":"SF-123"'}'</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>JavaScript (fetch)</Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeComment}>// List contacts with search</Text>
              <Text style={styles.codeText}>const res = await fetch(</Text>
              <Text style={styles.codeText}>  '{APP_URL}/api/v1/contacts?search=john',</Text>
              <Text style={styles.codeText}>  {'{ headers: { "X-API-Key": key } }'}</Text>
              <Text style={styles.codeText}>);</Text>
              <Text style={styles.codeText}>const {'{ contacts, total }'} = await res.json();</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Python (requests)</Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeComment}># Create a contact with CRM sync</Text>
              <Text style={styles.codeText}>import requests</Text>
              <Text style={styles.codeText}>{''}</Text>
              <Text style={styles.codeText}>r = requests.post(</Text>
              <Text style={styles.codeText}>    "{APP_URL}/api/v1/contacts",</Text>
              <Text style={styles.codeText}>    headers={"{'\"X-API-Key\": key}"},</Text>
              <Text style={styles.codeText}>    json={"{"}</Text>
              <Text style={styles.codeText}>        "first_name": "Jane",</Text>
              <Text style={styles.codeText}>        "phone": "+15559876543",</Text>
              <Text style={styles.codeText}>        "external_id": "HUB-456",</Text>
              <Text style={styles.codeText}>        "external_ids": {"{\"hubspot\": \"HUB-456\"}"}</Text>
              <Text style={styles.codeText}>    {"}"}</Text>
              <Text style={styles.codeText}>)</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Webhook Receiver (Node.js)</Text>
            <View style={styles.codeBlockMulti}>
              <Text style={styles.codeComment}>i'M On Social</Text>
              <Text style={styles.codeText}>app.post('/webhook', (req, res) =&gt; {'{'}</Text>
              <Text style={styles.codeText}>  const {'{ event, data }'} = req.body;</Text>
              <Text style={styles.codeText}>{''}</Text>
              <Text style={styles.codeText}>  if (event === 'contact.created') {'{'}</Text>
              <Text style={styles.codeText}>    syncToCRM(data);</Text>
              <Text style={styles.codeText}>  {'}'}</Text>
              <Text style={styles.codeText}>  res.sendStatus(200);</Text>
              <Text style={styles.codeText}>{'}'});</Text>
            </View>
          </View>
        </>
      )}

      {/* Zapier / Make Guide */}
      {docsSection === 'zapier' && (
        <>
          <Text style={styles.docSectionTitle}>Zapier / Make.com Integration</Text>

          <View style={styles.docCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <View style={[styles.docIconBadge, { backgroundColor: '#FF4A0020' }]}>
                <Ionicons name="flash" size={16} color="#FF4A00" />
              </View>
              <Text style={styles.docCardTitle}>Zapier Setup</Text>
            </View>
            <View style={styles.stepList}>
              <Text style={styles.stepItem}>1. Create a Zap with "Webhooks by Zapier" as trigger</Text>
              <Text style={styles.stepItem}>2. Choose "Catch Hook" as trigger event</Text>
              <Text style={styles.stepItem}>3. Copy the webhook URL from Zapier</Text>
              <Text style={styles.stepItem}>i'M On Social</Text>
              <Text style={styles.stepItem}>5. Paste the Zapier URL and select your events</Text>
              <Text style={styles.stepItem}>6. Test the webhook  - Zapier will receive sample data</Text>
              <Text style={styles.stepItem}>i'M On Social</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <View style={[styles.docIconBadge, { backgroundColor: '#6C63FF20' }]}>
                <Ionicons name="git-network" size={16} color="#6C63FF" />
              </View>
              <Text style={styles.docCardTitle}>Make.com (Integromat)</Text>
            </View>
            <View style={styles.stepList}>
              <Text style={styles.stepItem}>1. Create a scenario with "Custom Webhook" module</Text>
              <Text style={styles.stepItem}>2. Copy the webhook URL</Text>
              <Text style={styles.stepItem}>i'M On Social</Text>
              <Text style={styles.stepItem}>4. Run once to establish data structure</Text>
              <Text style={styles.stepItem}>5. Add action modules to your destination</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Popular Automations</Text>
            <View style={styles.stepList}>
              <Text style={styles.stepItem}>i'M On Social</Text>
              <Text style={styles.stepItem}>Review submitted → Notify Slack channel</Text>
              <Text style={styles.stepItem}>Message received → Log in Google Sheets</Text>
              <Text style={styles.stepItem}>Contact tagged "HOT" → Add to HubSpot sequence</Text>
              <Text style={styles.stepItem}>Campaign completed → Update DMS record</Text>
              <Text style={styles.stepItem}>User deactivated → Alert admin via email</Text>
            </View>
          </View>

          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Two-Way Sync</Text>
            <Text style={styles.docParagraph}>
              Use the API to push data INTO i'M On Social and webhooks to push data OUT.
              Map your CRM IDs using the external_id and external_ids fields on contacts and users for bidirectional sync.
            </Text>
          </View>
        </>
      )}

      {/* Swagger link */}
      <TouchableOpacity
        style={styles.fullDocsButton}
        onPress={() => Linking.openURL(`${APP_URL}/api/docs`)}
        data-testid="swagger-link"
      >
        <Ionicons name="document-text-outline" size={20} color="#007AFF" />
        <Text style={styles.fullDocsText}>Interactive API Docs (Swagger)</Text>
      </TouchableOpacity>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Integrations</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabBar}>
        {[
          { key: 'api-keys', label: 'API Keys', icon: 'key' },
          { key: 'webhooks', label: 'Webhooks', icon: 'git-branch' },
          { key: 'crm', label: 'RMS', icon: 'people' },
          { key: 'dms', label: 'DMS', icon: 'car' },
          { key: 'docs', label: 'Docs', icon: 'document-text' },
        ].map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.activeTab]}
            onPress={() => setActiveTab(tab.key as TabType)}
          >
            <Ionicons 
              name={tab.icon as any} 
              size={18} 
              color={activeTab === tab.key ? '#007AFF' : colors.textSecondary} 
            />
            <Text style={[styles.tabText, activeTab === tab.key && styles.activeTabText]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView style={styles.content}>
        {activeTab === 'api-keys' && renderApiKeysTab()}
        {activeTab === 'webhooks' && renderWebhooksTab()}
        {activeTab === 'crm' && (
          <>
            {renderProvidersTab('crm')}
            {renderCrmTimelineSettings()}
          </>
        )}
        {activeTab === 'dms' && renderProvidersTab('dms')}
        {activeTab === 'docs' && renderDocsTab()}
      </ScrollView>

      {/* New API Key Modal */}
      <WebModal visible={showNewKeyModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Create API Key</Text>
            
            {newlyCreatedKey ? (
              <>
                <View style={styles.keyCreatedBox}>
                  <Ionicons name="checkmark-circle" size={48} color="#34C759" />
                  <Text style={styles.keyCreatedTitle}>Key Created!</Text>
                  <Text style={styles.keyCreatedWarning}>
                    Copy this key now - it won't be shown again
                  </Text>
                  <View style={styles.keyDisplay}>
                    <Text style={styles.keyText} selectable>{newlyCreatedKey}</Text>
                    <TouchableOpacity onPress={() => copyToClipboard(newlyCreatedKey)}>
                      <Ionicons name="copy" size={24} color="#007AFF" />
                    </TouchableOpacity>
                  </View>
                </View>
                <TouchableOpacity
                  style={styles.modalButton}
                  onPress={() => {
                    setShowNewKeyModal(false);
                    setNewlyCreatedKey(null);
                  }}
                >
                  <Text style={styles.modalButtonText}>Done</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <Text style={styles.modalLabel}>Key Name</Text>
                <TextInput
                  style={styles.modalInput}
                  value={newKeyName}
                  onChangeText={setNewKeyName}
                  placeholder="e.g., Zapier Integration"
                  placeholderTextColor={colors.textSecondary}
                />
                
                <View style={styles.modalActions}>
                  <TouchableOpacity
                    style={styles.modalCancelButton}
                    onPress={() => setShowNewKeyModal(false)}
                  >
                    <Text style={styles.modalCancelText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.modalButton, !newKeyName.trim() && styles.modalButtonDisabled]}
                    onPress={createApiKey}
                    disabled={!newKeyName.trim() || creatingKey}
                  >
                    {creatingKey ? (
                      <ActivityIndicator size="small" color={colors.text} />
                    ) : (
                      <Text style={styles.modalButtonText}>Create Key</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </WebModal>

      {/* New Webhook Modal */}
      <WebModal visible={showNewWebhookModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Create Webhook</Text>
            
            <Text style={styles.modalLabel}>Name</Text>
            <TextInput
              style={styles.modalInput}
              value={newWebhook.name}
              onChangeText={(text) => setNewWebhook(prev => ({ ...prev, name: text }))}
              placeholder="e.g., Zapier - New Contacts"
              placeholderTextColor={colors.textSecondary}
            />
            
            <Text style={styles.modalLabel}>Endpoint URL</Text>
            <TextInput
              style={styles.modalInput}
              value={newWebhook.url}
              onChangeText={(text) => setNewWebhook(prev => ({ ...prev, url: text }))}
              placeholder="https://hooks.zapier.com/..."
              placeholderTextColor={colors.textSecondary}
              autoCapitalize="none"
              keyboardType="url"
            />
            
            <Text style={styles.modalLabel}>Events</Text>
            <ScrollView style={styles.eventsScrollView} nestedScrollEnabled>
              {Object.entries(webhookEvents).map(([event, description]) => (
                <TouchableOpacity
                  key={event}
                  style={[
                    styles.eventOption,
                    newWebhook.events.includes(event) && styles.eventOptionSelected
                  ]}
                  onPress={() => {
                    setNewWebhook(prev => ({
                      ...prev,
                      events: prev.events.includes(event)
                        ? prev.events.filter(e => e !== event)
                        : [...prev.events, event]
                    }));
                  }}
                >
                  <View style={styles.eventCheckbox}>
                    {newWebhook.events.includes(event) && (
                      <Ionicons name="checkmark" size={16} color="#007AFF" />
                    )}
                  </View>
                  <View style={styles.eventInfo}>
                    <Text style={styles.eventName}>{event}</Text>
                    <Text style={styles.eventDesc}>{description}</Text>
                  </View>
                </TouchableOpacity>
              ))}
            </ScrollView>
            
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.modalCancelButton}
                onPress={() => setShowNewWebhookModal(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, (!newWebhook.name.trim() || !newWebhook.url.trim()) && styles.modalButtonDisabled]}
                onPress={createWebhook}
                disabled={!newWebhook.name.trim() || !newWebhook.url.trim()}
              >
                <Text style={styles.modalButtonText}>Create Webhook</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </WebModal>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.bg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  tabBar: {
    flexGrow: 0,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 6,
  },
  activeTab: {
    borderBottomWidth: 2,
    borderBottomColor: '#007AFF',
  },
  tabText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  activeTabText: {
    color: '#007AFF',
    fontWeight: '600',
  },
  content: {
    flex: 1,
  },
  tabContent: {
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
  },
  sectionSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  addButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 16,
    color: colors.text,
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
    textAlign: 'center',
  },
  keyCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  keyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  keyName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  activeBadge: {
    backgroundColor: '#34C75920',
  },
  revokedBadge: {
    backgroundColor: '#FF3B3020',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#34C759',
  },
  keyPrefix: {
    fontSize: 13,
    fontFamily: 'monospace',
    color: colors.textSecondary,
    marginTop: 8,
  },
  keyMeta: {
    fontSize: 12,
    color: '#6E6E73',
    marginTop: 4,
  },
  keyActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
  },
  keyRequests: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  revokeButton: {
    fontSize: 14,
    color: '#FF3B30',
    fontWeight: '600',
  },
  webhookCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  webhookHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  webhookName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  webhookUrl: {
    fontSize: 13,
    fontFamily: 'monospace',
    color: colors.textSecondary,
    marginTop: 8,
  },
  webhookEvents: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 12,
    gap: 6,
  },
  eventChip: {
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  eventChipText: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  moreEvents: {
    fontSize: 11,
    color: colors.textSecondary,
    alignSelf: 'center',
  },
  webhookActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
  },
  webhookStats: {
    fontSize: 12,
    color: '#6E6E73',
  },
  testButton: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '600',
  },
  connectedSection: {
    marginBottom: 24,
  },
  availableSection: {
    marginTop: 8,
  },
  subsectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
  },
  connectionCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  connectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  connectionName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  syncBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  syncSuccess: {
    backgroundColor: '#34C75920',
  },
  syncError: {
    backgroundColor: '#FF3B3020',
  },
  syncPending: {
    backgroundColor: '#FF950020',
  },
  syncText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  lastSync: {
    fontSize: 12,
    color: '#6E6E73',
    marginTop: 8,
  },
  providerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  providerInfo: {
    flex: 1,
  },
  providerName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  providerDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  docCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  docCardTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  docCardText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  codeInline: {
    fontFamily: 'monospace',
    backgroundColor: colors.surface,
    color: '#FF9500',
  },
  codeBlock: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 12,
  },
  codeText: {
    fontFamily: 'monospace',
    fontSize: 14,
    color: '#34C759',
  },
  endpointsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
    marginBottom: 12,
  },
  endpointCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  endpointHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  endpointName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  methodBadges: {
    flexDirection: 'row',
    gap: 4,
  },
  methodBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: colors.surface,
  },
  methodGET: {
    backgroundColor: '#34C75930',
  },
  methodPOST: {
    backgroundColor: '#007AFF30',
  },
  methodPUT: {
    backgroundColor: '#FF950030',
  },
  methodDELETE: {
    backgroundColor: '#FF3B3030',
  },
  methodText: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  endpointPath: {
    fontSize: 13,
    fontFamily: 'monospace',
    color: colors.textSecondary,
    marginTop: 8,
  },
  endpointDesc: {
    fontSize: 13,
    color: '#6E6E73',
    marginTop: 4,
  },
  fullDocsButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    marginBottom: 40,
    gap: 8,
  },
  fullDocsText: {
    fontSize: 15,
    color: '#007AFF',
    fontWeight: '500',
  },
  docNavPill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  docNavPillActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  docNavText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  docNavTextActive: {
    color: colors.text,
  },
  docSectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 12,
  },
  docParagraph: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: 12,
  },
  codeBlockMulti: {
    backgroundColor: '#0D1117',
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: '#21262D',
  },
  codeComment: {
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#6E7681',
    marginBottom: 4,
  },
  docIconBadge: {
    width: 30,
    height: 30,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  endpointRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  methodTag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    minWidth: 50,
    alignItems: 'center',
  },
  methodTagText: {
    fontSize: 11,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  endpointPathText: {
    fontSize: 13,
    fontFamily: 'monospace',
    color: colors.borderLight,
  },
  endpointDescText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  endpointParams: {
    fontSize: 11,
    color: '#6E6E73',
    fontStyle: 'italic',
    marginTop: 4,
  },
  endpointBody: {
    fontSize: 11,
    fontFamily: 'monospace',
    color: '#FF9500',
    marginTop: 4,
  },
  webhookEventRow: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  eventDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  webhookEventName: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    fontFamily: 'monospace',
  },
  webhookEventDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
    marginLeft: 16,
  },
  webhookEventPayload: {
    fontSize: 11,
    fontFamily: 'monospace',
    color: '#6E6E73',
    marginTop: 4,
    marginLeft: 16,
  },
  stepList: {
    gap: 8,
  },
  stepItem: {
    fontSize: 14,
    color: '#C7C7CC',
    lineHeight: 20,
    paddingLeft: 4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '80%',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 20,
    textAlign: 'center',
  },
  modalLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 8,
  },
  modalInput: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: colors.text,
    marginBottom: 16,
  },
  modalActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  modalCancelButton: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 16,
    color: colors.text,
    fontWeight: '600',
  },
  modalButton: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    backgroundColor: '#007AFF',
    alignItems: 'center',
  },
  modalButtonDisabled: {
    backgroundColor: '#3C3C3E',
  },
  modalButtonText: {
    fontSize: 16,
    color: colors.text,
    fontWeight: '600',
  },
  keyCreatedBox: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  keyCreatedTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 12,
  },
  keyCreatedWarning: {
    fontSize: 14,
    color: '#FF9500',
    marginTop: 8,
    textAlign: 'center',
  },
  keyDisplay: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginTop: 16,
    gap: 8,
  },
  keyText: {
    flex: 1,
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#34C759',
  },
  eventsScrollView: {
    maxHeight: 200,
    marginBottom: 16,
  },
  eventOption: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  eventOptionSelected: {
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  eventCheckbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#3C3C3E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  eventInfo: {
    flex: 1,
  },
  eventName: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  eventDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
