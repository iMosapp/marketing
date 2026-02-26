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
  const router = useRouter();
  const { user } = useAuthStore();
const { showToast } = useToast();
    const [activeTab, setActiveTab] = useState<TabType>('api-keys');
  const [loading, setLoading] = useState(true);
  
  // API Keys
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [showNewKeysetShowNewKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  
  // Webhooks
  const [webhooks, setWebhooks] = useState<any[]>([]);
  const [webhookEvents, setWebhookEvents] = useState<Record<string, string>>({});
  const [showNewWebhooksetShowNewWebhookModal] = useState(false);
  const [newWebhook, setNewWebhook] = useState({ name: '', url: '', events: [] as string[] });
  
  // Providers
  const [providers, setProviders] = useState<{ crm: Record<string, Provider>; dms: Record<string, Provider> }>({ crm: {}, dms: {} });
  const [connections, setConnections] = useState<any[]>([]);
  
  // Docs
  const [apiDocs, setApiDocs] = useState<any>(null);

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
      const [keysRes, webhooksRes, eventsRes, providersRes, connectionsRes, docsRes] = await Promise.all([
        api.get(`/integrations/api-keys?store_id=${user.store_id}`),
        api.get(`/integrations/webhooks?store_id=${user.store_id}`),
        api.get('/integrations/webhooks/events'),
        api.get('/integrations/providers'),
        api.get(`/integrations/connections?store_id=${user.store_id}`),
        api.get('/integrations/docs/overview'),
      ]);
      
      setApiKeys(keysRes.data);
      setWebhooks(webhooksRes.data);
      setWebhookEvents(eventsRes.data);
      setProviders(providersRes.data);
      setConnections(connectionsRes.data);
      setApiDocs(docsRes.data);
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
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </View>
      
      {apiKeys.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="key-outline" size={48} color="#8E8E93" />
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
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </View>
      
      {webhooks.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="git-branch-outline" size={48} color="#8E8E93" />
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
              <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
            </TouchableOpacity>
          ))}
        </View>
      </View>
    );
  };

  const renderDocsTab = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionTitle}>API Documentation</Text>
      <Text style={styles.sectionSubtitle}>
        Everything you need to integrate with iMOs
      </Text>
      
      {apiDocs && (
        <>
          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Authentication</Text>
            <Text style={styles.docCardText}>
              Include your API key in the <Text style={styles.codeInline}>X-API-Key</Text> header
            </Text>
          </View>
          
          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Base URL</Text>
            <View style={styles.codeBlock}>
              <Text style={styles.codeText}>{apiDocs.base_url || '/api'}</Text>
              <TouchableOpacity onPress={() => copyToClipboard(apiDocs.base_url || '/api')}>
                <Ionicons name="copy-outline" size={18} color="#8E8E93" />
              </TouchableOpacity>
            </View>
          </View>
          
          <View style={styles.docCard}>
            <Text style={styles.docCardTitle}>Rate Limits</Text>
            <Text style={styles.docCardText}>
              {apiDocs.rate_limits?.requests_per_minute || 60} requests/minute
              {'\n'}{apiDocs.rate_limits?.requests_per_day || 10000} requests/day
            </Text>
          </View>
          
          <Text style={styles.endpointsTitle}>Endpoints</Text>
          {apiDocs.endpoints && Object.entries(apiDocs.endpoints).map(([name, endpoint]: [string, any]) => (
            <TouchableOpacity key={name} style={styles.endpointCard}>
              <View style={styles.endpointHeader}>
                <Text style={styles.endpointName}>{name.charAt(0).toUpperCase() + name.slice(1)}</Text>
                <View style={styles.methodBadges}>
                  {endpoint.methods?.map((method: string) => (
                    <View key={method} style={[styles.methodBadge, styles[`method${method}` as keyof typeof styles] || {}]}>
                      <Text style={styles.methodText}>{method}</Text>
                    </View>
                  ))}
                </View>
              </View>
              <Text style={styles.endpointPath}>{endpoint.base}</Text>
              <Text style={styles.endpointDesc}>{endpoint.description}</Text>
            </TouchableOpacity>
          ))}
          
          <TouchableOpacity 
            style={styles.fullDocsButton}
            onPress={() => Linking.openURL('/api/docs')}
          >
            <Ionicons name="document-text-outline" size={20} color="#007AFF" />
            <Text style={styles.fullDocsText}>View Full API Documentation (Swagger)</Text>
          </TouchableOpacity>
        </>
      )}
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
          <Ionicons name="chevron-back" size={24} color="#FFF" />
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
              color={activeTab === tab.key ? '#007AFF' : '#8E8E93'} 
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
        {activeTab === 'crm' && renderProvidersTab('crm')}
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
                  placeholderTextColor="#8E8E93"
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
                      <ActivityIndicator size="small" color="#FFF" />
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
              placeholderTextColor="#8E8E93"
            />
            
            <Text style={styles.modalLabel}>Endpoint URL</Text>
            <TextInput
              style={styles.modalInput}
              value={newWebhook.url}
              onChangeText={(text) => setNewWebhook(prev => ({ ...prev, url: text }))}
              placeholder="https://hooks.zapier.com/..."
              placeholderTextColor="#8E8E93"
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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#000',
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
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  tabBar: {
    flexGrow: 0,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
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
    color: '#8E8E93',
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
    color: '#FFF',
  },
  sectionSubtitle: {
    fontSize: 14,
    color: '#8E8E93',
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
    color: '#FFF',
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 4,
    textAlign: 'center',
  },
  keyCard: {
    backgroundColor: '#1C1C1E',
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
    color: '#FFF',
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
    color: '#8E8E93',
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
    color: '#8E8E93',
  },
  revokeButton: {
    fontSize: 14,
    color: '#FF3B30',
    fontWeight: '600',
  },
  webhookCard: {
    backgroundColor: '#1C1C1E',
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
    color: '#FFF',
  },
  webhookUrl: {
    fontSize: 13,
    fontFamily: 'monospace',
    color: '#8E8E93',
    marginTop: 8,
  },
  webhookEvents: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 12,
    gap: 6,
  },
  eventChip: {
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  eventChipText: {
    fontSize: 11,
    color: '#8E8E93',
  },
  moreEvents: {
    fontSize: 11,
    color: '#8E8E93',
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
    color: '#8E8E93',
    marginBottom: 12,
  },
  connectionCard: {
    backgroundColor: '#1C1C1E',
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
    color: '#FFF',
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
    color: '#8E8E93',
  },
  lastSync: {
    fontSize: 12,
    color: '#6E6E73',
    marginTop: 8,
  },
  providerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
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
    color: '#FFF',
  },
  providerDesc: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 4,
  },
  docCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  docCardTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 8,
  },
  docCardText: {
    fontSize: 14,
    color: '#8E8E93',
    lineHeight: 20,
  },
  codeInline: {
    fontFamily: 'monospace',
    backgroundColor: '#2C2C2E',
    color: '#FF9500',
  },
  codeBlock: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#2C2C2E',
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
    color: '#FFF',
    marginTop: 16,
    marginBottom: 12,
  },
  endpointCard: {
    backgroundColor: '#1C1C1E',
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
    color: '#FFF',
  },
  methodBadges: {
    flexDirection: 'row',
    gap: 4,
  },
  methodBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: '#2C2C2E',
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
    color: '#8E8E93',
  },
  endpointPath: {
    fontSize: 13,
    fontFamily: 'monospace',
    color: '#8E8E93',
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
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    gap: 8,
  },
  fullDocsText: {
    fontSize: 15,
    color: '#007AFF',
    fontWeight: '500',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '80%',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 20,
    textAlign: 'center',
  },
  modalLabel: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 8,
  },
  modalInput: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
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
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 16,
    color: '#FFF',
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
    color: '#FFF',
    fontWeight: '600',
  },
  keyCreatedBox: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  keyCreatedTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
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
    backgroundColor: '#2C2C2E',
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
    backgroundColor: '#2C2C2E',
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
    color: '#FFF',
  },
  eventDesc: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
});
