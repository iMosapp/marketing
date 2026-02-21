import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../../services/api';

export default function PartnerAgreementSigningPage() {
  const { agreementId, payment, session_id } = useLocalSearchParams();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [agreement, setAgreement] = useState<any>(null);
  const [signing, setSigning] = useState(false);
  const [processingPayment, setProcessingPayment] = useState(false);
  
  // Form state
  const [form, setForm] = useState({
    name: '',
    email: '',
    company: '',
    phone: '',
    address: '',
    city: '',
    state: '',
    zip_code: '',
    tax_id: '',
  });
  const [signature, setSignature] = useState('');
  const [signatureType, setSignatureType] = useState<'typed' | 'drawn'>('typed');
  const [agreedToTerms, setAgreedToTerms] = useState(false);

  useEffect(() => {
    loadAgreement();
  }, [agreementId]);

  useEffect(() => {
    // Handle payment return
    if (payment === 'success' && session_id) {
      checkPaymentStatus();
    }
  }, [payment, session_id]);

  const loadAgreement = async () => {
    try {
      const response = await api.get(`/partners/agreements/${agreementId}`);
      setAgreement(response.data);
      
      // Pre-fill if info exists
      if (response.data.partner_name) {
        setForm(prev => ({ ...prev, name: response.data.partner_name }));
      }
      if (response.data.partner_email) {
        setForm(prev => ({ ...prev, email: response.data.partner_email }));
      }
    } catch (error) {
      console.error('Error loading agreement:', error);
      Alert.alert('Error', 'Agreement not found or has expired');
    } finally {
      setLoading(false);
    }
  };

  const checkPaymentStatus = async () => {
    setProcessingPayment(true);
    try {
      // Poll for payment status
      let attempts = 0;
      const maxAttempts = 10;
      
      while (attempts < maxAttempts) {
        const response = await api.get(
          `/partners/agreements/${agreementId}/payment-status?session_id=${session_id}`
        );
        
        if (response.data.payment_status === 'paid') {
          Alert.alert('Payment Successful!', 'Welcome to the MVPLine Partner Program!');
          loadAgreement();
          break;
        }
        
        attempts++;
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    } catch (error) {
      console.error('Error checking payment:', error);
    } finally {
      setProcessingPayment(false);
    }
  };

  const handleSign = async () => {
    // Validation
    if (!form.name.trim()) {
      Alert.alert('Required', 'Please enter your name');
      return;
    }
    if (!form.email.trim()) {
      Alert.alert('Required', 'Please enter your email');
      return;
    }
    if (!signature.trim()) {
      Alert.alert('Required', 'Please sign the agreement');
      return;
    }
    if (!agreedToTerms) {
      Alert.alert('Required', 'Please agree to the terms');
      return;
    }
    
    setSigning(true);
    try {
      const response = await api.post(`/partners/agreements/${agreementId}/sign`, {
        ...form,
        signature,
        signature_type: signatureType,
        agreed_to_terms: agreedToTerms,
      });
      
      if (response.data.payment_required) {
        // Redirect to payment
        initiatePayment();
      } else {
        Alert.alert('Success!', 'Welcome to the MVPLine Partner Program!');
        loadAgreement();
      }
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to sign agreement');
    } finally {
      setSigning(false);
    }
  };

  const initiatePayment = async () => {
    try {
      const originUrl = Platform.OS === 'web' 
        ? window.location.origin 
        : 'https://mvpline.com';
      
      const response = await api.post(`/partners/agreements/${agreementId}/create-payment`, {
        origin_url: originUrl,
      });
      
      if (response.data.checkout_url) {
        if (Platform.OS === 'web') {
          window.location.href = response.data.checkout_url;
        } else {
          // For native, you'd use Linking or a WebView
          Alert.alert('Payment', 'Please complete payment in browser');
        }
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to initiate payment');
    }
  };

  const renderMarkdown = (content: string) => {
    // Simple markdown-like rendering
    const lines = content.split('\n');
    return lines.map((line, index) => {
      if (line.startsWith('# ')) {
        return <Text key={index} style={styles.mdH1}>{line.substring(2)}</Text>;
      }
      if (line.startsWith('## ')) {
        return <Text key={index} style={styles.mdH2}>{line.substring(3)}</Text>;
      }
      if (line.startsWith('- ')) {
        return (
          <View key={index} style={styles.mdListItem}>
            <Text style={styles.mdBullet}>•</Text>
            <Text style={styles.mdText}>{line.substring(2)}</Text>
          </View>
        );
      }
      if (line.startsWith('---')) {
        return <View key={index} style={styles.mdDivider} />;
      }
      if (line.trim() === '') {
        return <View key={index} style={{ height: 12 }} />;
      }
      return <Text key={index} style={styles.mdText}>{line}</Text>;
    });
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading agreement...</Text>
      </View>
    );
  }

  if (!agreement) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle" size={64} color="#FF3B30" />
        <Text style={styles.errorTitle}>Agreement Not Found</Text>
        <Text style={styles.errorText}>This agreement link is invalid or has expired.</Text>
      </View>
    );
  }

  if (agreement.status === 'signed') {
    return (
      <View style={styles.signedContainer}>
        <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
          <ScrollView contentContainerStyle={styles.signedContent}>
            <View style={styles.successBadge}>
              <Ionicons name="checkmark-circle" size={80} color="#34C759" />
            </View>
            <Text style={styles.signedTitle}>Agreement Signed!</Text>
            <Text style={styles.signedSubtitle}>
              Welcome to the MVPLine Partner Program
            </Text>
            
            <View style={styles.signedDetails}>
              <View style={styles.signedDetailRow}>
                <Text style={styles.signedDetailLabel}>Partner</Text>
                <Text style={styles.signedDetailValue}>
                  {agreement.signed_partner?.name}
                </Text>
              </View>
              <View style={styles.signedDetailRow}>
                <Text style={styles.signedDetailLabel}>Agreement Type</Text>
                <Text style={styles.signedDetailValue}>
                  {agreement.template_name}
                </Text>
              </View>
              {agreement.commission_tier && (
                <View style={styles.signedDetailRow}>
                  <Text style={styles.signedDetailLabel}>Commission Tier</Text>
                  <Text style={styles.signedDetailValue}>
                    {agreement.commission_tier.name} ({agreement.commission_tier.percentage}%)
                  </Text>
                </View>
              )}
              <View style={styles.signedDetailRow}>
                <Text style={styles.signedDetailLabel}>Signed On</Text>
                <Text style={styles.signedDetailValue}>
                  {new Date(agreement.signed_at).toLocaleDateString()}
                </Text>
              </View>
            </View>
            
            <Text style={styles.nextStepsTitle}>What's Next?</Text>
            <View style={styles.nextStep}>
              <Ionicons name="mail-outline" size={24} color="#007AFF" />
              <Text style={styles.nextStepText}>
                You'll receive a welcome email with your partner portal access
              </Text>
            </View>
            <View style={styles.nextStep}>
              <Ionicons name="link-outline" size={24} color="#007AFF" />
              <Text style={styles.nextStepText}>
                Your unique referral link will be activated within 24 hours
              </Text>
            </View>
          </ScrollView>
        </SafeAreaView>
      </View>
    );
  }

  if (agreement.status === 'pending_payment' && !processingPayment) {
    return (
      <View style={styles.paymentContainer}>
        <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
          <View style={styles.paymentContent}>
            <Ionicons name="card-outline" size={64} color="#FF9500" />
            <Text style={styles.paymentTitle}>Payment Required</Text>
            <Text style={styles.paymentSubtitle}>
              Complete your payment to activate your partnership
            </Text>
            
            <View style={styles.paymentAmount}>
              <Text style={styles.paymentAmountLabel}>Amount Due</Text>
              <Text style={styles.paymentAmountValue}>
                ${agreement.payment_amount?.toFixed(2)}
              </Text>
            </View>
            
            <TouchableOpacity
              style={styles.payButton}
              onPress={initiatePayment}
            >
              <Ionicons name="card" size={20} color="#FFF" />
              <Text style={styles.payButtonText}>Complete Payment</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  if (processingPayment) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Processing payment...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>{agreement.template_name}</Text>
          {agreement.commission_tier && (
            <View style={styles.tierBadge}>
              <Text style={styles.tierBadgeText}>
                {agreement.commission_tier.name} - {agreement.commission_tier.percentage}%
              </Text>
            </View>
          )}
        </View>

        <ScrollView style={styles.scrollView}>
          {/* Agreement Content */}
          <View style={styles.contentSection}>
            <Text style={styles.sectionTitle}>Agreement Terms</Text>
            <View style={styles.agreementContent}>
              {renderMarkdown(agreement.content || '')}
            </View>
          </View>

          {/* Partner Information Form */}
          <View style={styles.formSection}>
            <Text style={styles.sectionTitle}>Your Information</Text>
            
            <Text style={styles.formLabel}>Full Name *</Text>
            <TextInput
              style={styles.input}
              value={form.name}
              onChangeText={(text) => setForm(prev => ({ ...prev, name: text }))}
              placeholder="John Doe"
              placeholderTextColor="#8E8E93"
            />
            
            <Text style={styles.formLabel}>Email *</Text>
            <TextInput
              style={styles.input}
              value={form.email}
              onChangeText={(text) => setForm(prev => ({ ...prev, email: text }))}
              placeholder="john@company.com"
              placeholderTextColor="#8E8E93"
              keyboardType="email-address"
              autoCapitalize="none"
            />
            
            <Text style={styles.formLabel}>Company</Text>
            <TextInput
              style={styles.input}
              value={form.company}
              onChangeText={(text) => setForm(prev => ({ ...prev, company: text }))}
              placeholder="Your Company Name"
              placeholderTextColor="#8E8E93"
            />
            
            <Text style={styles.formLabel}>Phone</Text>
            <TextInput
              style={styles.input}
              value={form.phone}
              onChangeText={(text) => setForm(prev => ({ ...prev, phone: text }))}
              placeholder="(555) 123-4567"
              placeholderTextColor="#8E8E93"
              keyboardType="phone-pad"
            />
            
            <Text style={styles.formLabel}>Address</Text>
            <TextInput
              style={styles.input}
              value={form.address}
              onChangeText={(text) => setForm(prev => ({ ...prev, address: text }))}
              placeholder="123 Main St"
              placeholderTextColor="#8E8E93"
            />
            
            <View style={styles.addressRow}>
              <View style={{ flex: 2 }}>
                <Text style={styles.formLabel}>City</Text>
                <TextInput
                  style={styles.input}
                  value={form.city}
                  onChangeText={(text) => setForm(prev => ({ ...prev, city: text }))}
                  placeholder="City"
                  placeholderTextColor="#8E8E93"
                />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.formLabel}>State</Text>
                <TextInput
                  style={styles.input}
                  value={form.state}
                  onChangeText={(text) => setForm(prev => ({ ...prev, state: text }))}
                  placeholder="ST"
                  placeholderTextColor="#8E8E93"
                />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.formLabel}>ZIP</Text>
                <TextInput
                  style={styles.input}
                  value={form.zip_code}
                  onChangeText={(text) => setForm(prev => ({ ...prev, zip_code: text }))}
                  placeholder="12345"
                  placeholderTextColor="#8E8E93"
                  keyboardType="number-pad"
                />
              </View>
            </View>
            
            <Text style={styles.formLabel}>Tax ID / EIN (for payouts)</Text>
            <TextInput
              style={styles.input}
              value={form.tax_id}
              onChangeText={(text) => setForm(prev => ({ ...prev, tax_id: text }))}
              placeholder="XX-XXXXXXX"
              placeholderTextColor="#8E8E93"
            />
          </View>

          {/* Signature Section */}
          <View style={styles.signatureSection}>
            <Text style={styles.sectionTitle}>Digital Signature</Text>
            
            <View style={styles.signatureTypeToggle}>
              <TouchableOpacity
                style={[
                  styles.signatureTypeButton,
                  signatureType === 'typed' && styles.signatureTypeButtonActive
                ]}
                onPress={() => setSignatureType('typed')}
              >
                <Ionicons 
                  name="text" 
                  size={18} 
                  color={signatureType === 'typed' ? '#007AFF' : '#8E8E93'} 
                />
                <Text style={[
                  styles.signatureTypeText,
                  signatureType === 'typed' && styles.signatureTypeTextActive
                ]}>
                  Type Signature
                </Text>
              </TouchableOpacity>
            </View>
            
            <TextInput
              style={styles.signatureInput}
              value={signature}
              onChangeText={setSignature}
              placeholder="Type your full legal name"
              placeholderTextColor="#8E8E93"
            />
            
            {signature && (
              <View style={styles.signaturePreview}>
                <Text style={styles.signaturePreviewText}>{signature}</Text>
              </View>
            )}
            
            <TouchableOpacity
              style={styles.agreeRow}
              onPress={() => setAgreedToTerms(!agreedToTerms)}
            >
              <View style={[styles.checkbox, agreedToTerms && styles.checkboxChecked]}>
                {agreedToTerms && <Ionicons name="checkmark" size={16} color="#FFF" />}
              </View>
              <Text style={styles.agreeText}>
                I have read and agree to the terms of this agreement
              </Text>
            </TouchableOpacity>
            
            {agreement.payment_required && agreement.payment_amount && (
              <View style={styles.paymentNote}>
                <Ionicons name="information-circle" size={20} color="#FF9500" />
                <Text style={styles.paymentNoteText}>
                  A one-time payment of ${agreement.payment_amount.toFixed(2)} is required after signing
                </Text>
              </View>
            )}
            
            <TouchableOpacity
              style={[styles.signButton, !agreedToTerms && styles.signButtonDisabled]}
              onPress={handleSign}
              disabled={!agreedToTerms || signing}
            >
              {signing ? (
                <ActivityIndicator color="#FFF" />
              ) : (
                <>
                  <Ionicons name="create" size={20} color="#FFF" />
                  <Text style={styles.signButtonText}>
                    {agreement.payment_required ? 'Sign & Continue to Payment' : 'Sign Agreement'}
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
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
  loadingText: {
    color: '#FFF',
    marginTop: 16,
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  errorText: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  signedContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  signedContent: {
    padding: 24,
    alignItems: 'center',
  },
  successBadge: {
    marginTop: 40,
    marginBottom: 24,
  },
  signedTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
  },
  signedSubtitle: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 8,
  },
  signedDetails: {
    width: '100%',
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    marginTop: 32,
  },
  signedDetailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  signedDetailLabel: {
    fontSize: 14,
    color: '#8E8E93',
  },
  signedDetailValue: {
    fontSize: 14,
    color: '#FFF',
    fontWeight: '600',
  },
  nextStepsTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 32,
    marginBottom: 16,
    alignSelf: 'flex-start',
  },
  nextStep: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    width: '100%',
  },
  nextStepText: {
    flex: 1,
    fontSize: 14,
    color: '#FFF',
    marginLeft: 12,
  },
  paymentContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  paymentContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  paymentTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
    marginTop: 24,
  },
  paymentSubtitle: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  paymentAmount: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    marginTop: 32,
    width: '100%',
  },
  paymentAmountLabel: {
    fontSize: 14,
    color: '#8E8E93',
  },
  paymentAmountValue: {
    fontSize: 48,
    fontWeight: '700',
    color: '#34C759',
    marginTop: 8,
  },
  payButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 18,
    marginTop: 32,
    width: '100%',
    gap: 8,
  },
  payButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  header: {
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
  },
  tierBadge: {
    backgroundColor: '#34C75920',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginTop: 8,
  },
  tierBadgeText: {
    fontSize: 14,
    color: '#34C759',
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  contentSection: {
    padding: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 16,
  },
  agreementContent: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
  },
  mdH1: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 16,
  },
  mdH2: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 20,
    marginBottom: 12,
  },
  mdText: {
    fontSize: 14,
    color: '#CCC',
    lineHeight: 22,
  },
  mdListItem: {
    flexDirection: 'row',
    paddingLeft: 8,
    marginBottom: 8,
  },
  mdBullet: {
    fontSize: 14,
    color: '#8E8E93',
    marginRight: 8,
  },
  mdDivider: {
    height: 1,
    backgroundColor: '#3C3C3E',
    marginVertical: 20,
  },
  formSection: {
    padding: 20,
    paddingTop: 0,
  },
  formLabel: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  addressRow: {
    flexDirection: 'row',
  },
  signatureSection: {
    padding: 20,
    paddingTop: 0,
  },
  signatureTypeToggle: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  signatureTypeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginRight: 12,
    gap: 8,
  },
  signatureTypeButtonActive: {
    backgroundColor: '#007AFF20',
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  signatureTypeText: {
    fontSize: 14,
    color: '#8E8E93',
  },
  signatureTypeTextActive: {
    color: '#007AFF',
    fontWeight: '600',
  },
  signatureInput: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
    marginBottom: 16,
  },
  signaturePreview: {
    backgroundColor: '#FFF',
    borderRadius: 10,
    padding: 20,
    alignItems: 'center',
    marginBottom: 16,
  },
  signaturePreviewText: {
    fontSize: 28,
    fontStyle: 'italic',
    color: '#000',
    fontFamily: Platform.OS === 'ios' ? 'Zapfino' : 'cursive',
  },
  agreeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#8E8E93',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  checkboxChecked: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  agreeText: {
    flex: 1,
    fontSize: 14,
    color: '#FFF',
  },
  paymentNote: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF950020',
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
    gap: 10,
  },
  paymentNoteText: {
    flex: 1,
    fontSize: 13,
    color: '#FF9500',
  },
  signButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#34C759',
    borderRadius: 12,
    padding: 18,
    gap: 10,
  },
  signButtonDisabled: {
    backgroundColor: '#3C3C3E',
  },
  signButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
});
