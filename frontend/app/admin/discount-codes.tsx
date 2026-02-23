import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Switch,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';

const DISCOUNT_TIERS = [5, 10, 15, 20, 25];

interface DiscountCode {
  _id: string;
  code: string;
  discount_percent: number;
  max_uses: number | null;
  times_used: number;
  plan_types: string[];
  description: string;
  status: string;
  expires_at: string;
  created_at: string;
}

export default function DiscountCodesPage() {
  const router = useRouter();
  const [codes, setCodes] = useState<DiscountCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  
  // Form state
  const [customCode, setCustomCode] = useState('');
  const [discountPercent, setDiscountPercent] = useState(10);
  const [maxUses, setMaxUses] = useState('');
  const [expiresDays, setExpiresDays] = useState('90');
  const [description, setDescription] = useState('');
  const [forIndividual, setForIndividual] = useState(true);
  const [forStore, setForStore] = useState(true);
  
  useEffect(() => {
    loadCodes();
  }, []);
  
  const loadCodes = async () => {
    try {
      const response = await api.get('/subscriptions/discount-codes?active_only=false');
      setCodes(response.data);
    } catch (error) {
      console.error('Error loading codes:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleCreateCode = async () => {
    if (!forIndividual && !forStore) {
      showSimpleAlert('Error', 'Select at least one plan type');
      return;
    }
    
    setCreating(true);
    
    try {
      const planTypes = [];
      if (forIndividual) planTypes.push('individual');
      if (forStore) planTypes.push('store');
      
      const response = await api.post('/subscriptions/discount-codes', {
        code: customCode || undefined,
        discount_percent: discountPercent,
        max_uses: maxUses ? parseInt(maxUses) : null,
        expires_days: parseInt(expiresDays) || 90,
        description: description,
        plan_types: planTypes,
      });
      
      showSimpleAlert(
        'Code Created',
        `Discount code ${response.data.code} created successfully!`
      );
      
      // Reset form
      setCustomCode('');
      setDescription('');
      setMaxUses('');
      setShowCreateForm(false);
      
      // Reload codes
      loadCodes();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to create code');
    } finally {
      setCreating(false);
    }
  };
  
  const handleDeactivate = (code: DiscountCode) => {
    showConfirm(
      'Deactivate Code',
      `Are you sure you want to deactivate ${code.code}?`,
      async () => {
        try {
          await api.delete(`/subscriptions/discount-codes/${code._id}`);
          loadCodes();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to deactivate code');
        }
      },
      undefined,
      'Deactivate',
      'Cancel'
    );
  };
  
  const copyToClipboard = async (text: string) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        showSimpleAlert('Copied', `${text} copied to clipboard`);
      }
    } catch (error) {
      console.error('Copy failed:', error);
    }
  };
  
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Discount Codes</Text>
        <TouchableOpacity onPress={() => setShowCreateForm(!showCreateForm)}>
          <Ionicons name={showCreateForm ? "close" : "add"} size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>
      
      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Create Form */}
        {showCreateForm && (
          <View style={styles.createForm}>
            <Text style={styles.formTitle}>Generate New Code</Text>
            
            <TextInput
              style={styles.input}
              placeholder="Custom code (optional - leave blank for auto)"
              placeholderTextColor="#8E8E93"
              value={customCode}
              onChangeText={setCustomCode}
              autoCapitalize="characters"
              maxLength={12}
            />
            
            <Text style={styles.inputLabel}>Discount Percentage</Text>
            <View style={styles.discountPicker}>
              {DISCOUNT_TIERS.map((pct) => (
                <TouchableOpacity
                  key={pct}
                  style={[styles.discountOption, discountPercent === pct && styles.discountOptionActive]}
                  onPress={() => setDiscountPercent(pct)}
                >
                  <Text style={[styles.discountOptionText, discountPercent === pct && styles.discountOptionTextActive]}>
                    {pct}%
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            
            <View style={styles.inputRow}>
              <View style={styles.inputHalf}>
                <Text style={styles.inputLabel}>Max Uses (blank = unlimited)</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Unlimited"
                  placeholderTextColor="#8E8E93"
                  value={maxUses}
                  onChangeText={setMaxUses}
                  keyboardType="number-pad"
                />
              </View>
              <View style={styles.inputHalf}>
                <Text style={styles.inputLabel}>Expires In (days)</Text>
                <TextInput
                  style={styles.input}
                  placeholder="90"
                  placeholderTextColor="#8E8E93"
                  value={expiresDays}
                  onChangeText={setExpiresDays}
                  keyboardType="number-pad"
                />
              </View>
            </View>
            
            <TextInput
              style={styles.input}
              placeholder="Description (optional)"
              placeholderTextColor="#8E8E93"
              value={description}
              onChangeText={setDescription}
            />
            
            <Text style={styles.inputLabel}>Valid For Plan Types</Text>
            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Individual Plans</Text>
              <Switch
                value={forIndividual}
                onValueChange={setForIndividual}
                trackColor={{ false: '#2C2C2E', true: '#007AFF' }}
              />
            </View>
            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Account Plans</Text>
              <Switch
                value={forStore}
                onValueChange={setForStore}
                trackColor={{ false: '#2C2C2E', true: '#007AFF' }}
              />
            </View>
            
            <TouchableOpacity
              style={[styles.createButton, creating && styles.createButtonDisabled]}
              onPress={handleCreateCode}
              disabled={creating}
            >
              {creating ? (
                <ActivityIndicator color="#FFF" />
              ) : (
                <>
                  <Ionicons name="ticket" size={20} color="#FFF" />
                  <Text style={styles.createButtonText}>Generate Code</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}
        
        {/* Codes List */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Active Codes ({codes.filter(c => c.status === 'active').length})</Text>
          
          {loading ? (
            <ActivityIndicator color="#007AFF" style={{ marginTop: 20 }} />
          ) : codes.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="ticket-outline" size={48} color="#2C2C2E" />
              <Text style={styles.emptyText}>No discount codes yet</Text>
              <Text style={styles.emptySubtext}>Create your first code above</Text>
            </View>
          ) : (
            codes.map((code) => (
              <View key={code._id} style={[styles.codeCard, code.status !== 'active' && styles.codeCardInactive]}>
                <View style={styles.codeHeader}>
                  <TouchableOpacity onPress={() => copyToClipboard(code.code)}>
                    <View style={styles.codeRow}>
                      <Text style={styles.codeText}>{code.code}</Text>
                      <Ionicons name="copy-outline" size={16} color="#8E8E93" />
                    </View>
                  </TouchableOpacity>
                  <View style={[styles.discountBadge, { backgroundColor: `${getDiscountColor(code.discount_percent)}20` }]}>
                    <Text style={[styles.discountBadgeText, { color: getDiscountColor(code.discount_percent) }]}>
                      {code.discount_percent}% OFF
                    </Text>
                  </View>
                </View>
                
                {code.description && (
                  <Text style={styles.codeDescription}>{code.description}</Text>
                )}
                
                <View style={styles.codeDetails}>
                  <View style={styles.codeDetail}>
                    <Ionicons name="repeat" size={14} color="#8E8E93" />
                    <Text style={styles.codeDetailText}>
                      {code.times_used} / {code.max_uses || '∞'} uses
                    </Text>
                  </View>
                  <View style={styles.codeDetail}>
                    <Ionicons name="calendar" size={14} color="#8E8E93" />
                    <Text style={styles.codeDetailText}>
                      Expires {formatDate(code.expires_at)}
                    </Text>
                  </View>
                </View>
                
                <View style={styles.codePlanTypes}>
                  {code.plan_types.map((type) => (
                    <View key={type} style={styles.planTypeBadge}>
                      <Ionicons name={type === 'individual' ? 'person' : 'storefront'} size={12} color="#8E8E93" />
                      <Text style={styles.planTypeText}>{type}</Text>
                    </View>
                  ))}
                </View>
                
                {code.status === 'active' && (
                  <TouchableOpacity
                    style={styles.deactivateButton}
                    onPress={() => handleDeactivate(code)}
                  >
                    <Text style={styles.deactivateButtonText}>Deactivate</Text>
                  </TouchableOpacity>
                )}
                
                {code.status !== 'active' && (
                  <View style={styles.inactiveBadge}>
                    <Text style={styles.inactiveBadgeText}>INACTIVE</Text>
                  </View>
                )}
              </View>
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function getDiscountColor(percent: number): string {
  if (percent >= 20) return '#34C759';
  if (percent >= 15) return '#30B0C7';
  if (percent >= 10) return '#007AFF';
  return '#8E8E93';
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
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
    width: 40,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
  },
  createForm: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    marginTop: 16,
  },
  formTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 16,
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 8,
  },
  inputRow: {
    flexDirection: 'row',
    gap: 12,
  },
  inputHalf: {
    flex: 1,
  },
  discountPicker: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  discountOption: {
    flex: 1,
    backgroundColor: '#2C2C2E',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  discountOptionActive: {
    backgroundColor: '#007AFF',
  },
  discountOptionText: {
    fontSize: 15,
    color: '#8E8E93',
    fontWeight: '600',
  },
  discountOptionTextActive: {
    color: '#FFF',
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  switchLabel: {
    fontSize: 16,
    color: '#FFF',
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#34C759',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    gap: 8,
  },
  createButtonDisabled: {
    opacity: 0.6,
  },
  createButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  section: {
    marginTop: 24,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 12,
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
  },
  codeCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  codeCardInactive: {
    opacity: 0.5,
  },
  codeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  codeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  codeText: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    fontFamily: 'monospace',
  },
  discountBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  discountBadgeText: {
    fontSize: 14,
    fontWeight: '700',
  },
  codeDescription: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 12,
  },
  codeDetails: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 12,
  },
  codeDetail: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  codeDetailText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  codePlanTypes: {
    flexDirection: 'row',
    gap: 8,
  },
  planTypeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  planTypeText: {
    fontSize: 12,
    color: '#8E8E93',
    textTransform: 'capitalize',
  },
  deactivateButton: {
    marginTop: 12,
    paddingVertical: 8,
    alignItems: 'center',
  },
  deactivateButtonText: {
    fontSize: 14,
    color: '#FF3B30',
    fontWeight: '500',
  },
  inactiveBadge: {
    marginTop: 12,
    alignItems: 'center',
  },
  inactiveBadgeText: {
    fontSize: 12,
    color: '#8E8E93',
    fontWeight: '600',
  },
});
