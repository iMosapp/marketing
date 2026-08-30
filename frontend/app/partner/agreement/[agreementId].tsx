import React, {
  useState, useEffect, useRef } from 'react';
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
import { useToast } from '../../../components/common/Toast';
import { showAlert, showSimpleAlert } from '../../../services/alert';

export default function PartnerAgreementSigningPage() {
  const { agreementId, payment, session_id } = useLocalSearchParams();
  const router = useRouter();
const { showToast } = useToast();
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
      showAlert('Error', 'Agreement not found or has expired');
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
          showAlert('Payment Successful!', "Welcome to the I'm On Social Partner Program!");
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

  const [w9Uploading, setW9Uploading] = useState(false);
  const [w9Uploaded, setW9Uploaded] = useState(false);
  const [w9Mode, setW9Mode] = useState<'choose' | 'digital' | 'upload'>('choose');

  // Digital W-9 form state
  const [w9Form, setW9Form] = useState({
    legal_name: '',
    business_name: '',
    tax_classification: 'individual',
    address: '',
    city_state_zip: '',
    tin: '',
    signature: '',
  });

  const TAX_CLASSES = [
    { key: 'individual', label: 'Individual / Sole Proprietor' },
    { key: 'c_corp',     label: 'C Corporation' },
    { key: 's_corp',     label: 'S Corporation' },
    { key: 'partnership',label: 'Partnership' },
    { key: 'llc',        label: 'LLC' },
    { key: 'other',      label: 'Other' },
  ];

  const handleW9Digital = async () => {
    if (!w9Form.legal_name.trim()) { showSimpleAlert('Required', 'Please enter your legal name.'); return; }
    if (!w9Form.tin.trim()) { showSimpleAlert('Required', 'Please enter your SSN or EIN.'); return; }
    if (!w9Form.signature.trim()) { showSimpleAlert('Required', 'Please type your signature to certify.'); return; }
    setW9Uploading(true);
    try {
      await api.post(`/partners/agreements/${agreementId}/w9-digital`, {
        ...w9Form,
        ip_address: 'unknown',
      });
      setW9Uploaded(true);
      setW9Mode('choose');
      showSimpleAlert('W-9 Submitted', 'Your W-9 has been received. We\'ll verify it within 1-2 business days.');
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to submit W-9.');
    } finally { setW9Uploading(false); }
  };

  const handleW9Upload = async (useCamera = false) => {
    if (Platform.OS !== 'web') {
      try {
        const { launchImageLibraryAsync, launchCameraAsync, MediaTypeOptions, requestCameraPermissionsAsync } = await import('expo-image-picker');
        let result;
        if (useCamera) {
          const { status } = await requestCameraPermissionsAsync();
          if (status !== 'granted') { showSimpleAlert('Permission needed', 'Allow camera access to photograph your W-9.'); return; }
          result = await launchCameraAsync({ mediaTypes: MediaTypeOptions.Images, quality: 0.9 });
        } else {
          result = await launchImageLibraryAsync({ mediaTypes: MediaTypeOptions.All, quality: 0.9 });
        }
        if (!result.canceled && result.assets?.[0]) {
          const asset = result.assets[0];
          const fd = new FormData();
          const ext = asset.uri.split('.').pop() || 'jpg';
          const mime = ext === 'pdf' ? 'application/pdf' : `image/${ext}`;
          fd.append('file', { uri: asset.uri, name: `w9.${ext}`, type: mime } as any);
          setW9Uploading(true);
          await api.post(`/partners/agreements/${agreementId}/w9`, fd);
          setW9Uploaded(true);
          setW9Mode('choose');
          showSimpleAlert('W-9 Submitted', 'Your W-9 has been received. We\'ll verify it within 1-2 business days.');
        }
      } catch { showSimpleAlert('Error', 'Failed to upload W-9. Please try again.'); }
      finally { setW9Uploading(false); }
    } else {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.pdf,.png,.jpg,.jpeg';
      input.onchange = async (e: any) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const fd = new FormData();
        fd.append('file', file);
        setW9Uploading(true);
        try {
          await api.post(`/partners/agreements/${agreementId}/w9`, fd);
          setW9Uploaded(true);
          setW9Mode('choose');
          showSimpleAlert('W-9 Submitted', 'Your W-9 has been received. We\'ll verify it within 1-2 business days.');
        } catch { showSimpleAlert('Error', 'Failed to upload W-9.'); }
        finally { setW9Uploading(false); }
      };
      input.click();
    }
  };

  const handleSign = async () => {
    // Validation
    if (!form.name.trim()) {
      showAlert('Required', 'Please enter your name');
      return;
    }
    if (!form.email.trim()) {
      showAlert('Required', 'Please enter your email');
      return;
    }
    if (!signature.trim()) {
      showAlert('Required', 'Please sign the agreement');
      return;
    }
    if (!agreedToTerms) {
      showAlert('Required', 'Please agree to the terms');
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
        showAlert('Success!', "Welcome to the I'm On Social Partner Program!");
        loadAgreement();
      }
    } catch (error: any) {
      showAlert('Error', error.response?.data?.detail || 'Failed to sign agreement');
    } finally {
      setSigning(false);
    }
  };

  const initiatePayment = async () => {
    try {
      const originUrl = Platform.OS === 'web' 
        ? (process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com')
        : 'https://app.imonsocial.com';
      
      const response = await api.post(`/partners/agreements/${agreementId}/create-payment`, {
        origin_url: originUrl,
      });
      
      if (response.data.checkout_url) {
        if (Platform.OS === 'web') {
          window.location.href = response.data.checkout_url;
        } else {
          // For native, you'd use Linking or a WebView
          showAlert('Payment', 'Please complete payment in browser');
        }
      }
    } catch (error) {
      showAlert('Error', 'Failed to initiate payment');
    }
  };

  /** Render a text string with inline **bold** and *italic* markers into React Native Text spans. */
  const renderInline = (text: string, baseStyle: any, key: string) => {
    // Strip wrapping italic markers like *(text)* at line level
    const cleaned = text.replace(/^\*\((.*)\)\*$/, '$1').replace(/^\*(.*)\*$/, '$1');
    if (!cleaned.includes('**') && !cleaned.includes('*')) {
      return <Text key={key} style={baseStyle}>{cleaned}</Text>;
    }
    // Split on **bold** first, then *italic*
    const boldParts = cleaned.split(/\*\*(.*?)\*\*/);
    return (
      <Text key={key} style={baseStyle}>
        {boldParts.map((p, pi) => {
          if (pi % 2 === 1) return <Text key={`${key}-b${pi}`} style={{ fontWeight: '700', color: '#FFF' }}>{p}</Text>;
          // Check for *italic* within non-bold segments
          if (p.includes('*')) {
            const italicParts = p.split(/\*(.*?)\*/);
            return italicParts.map((ip, ii) =>
              ii % 2 === 1
                ? <Text key={`${key}-i${ii}`} style={{ fontStyle: 'italic' }}>{ip}</Text>
                : ip
            );
          }
          return p;
        })}
      </Text>
    );
  };

  const renderMarkdown = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, index) => {
      const key = `md-${index}`;
      if (line.startsWith('# '))  return <Text key={key} style={styles.mdH1}>{line.substring(2)}</Text>;
      if (line.startsWith('## ')) return <Text key={key} style={styles.mdH2}>{line.substring(3)}</Text>;
      if (line.startsWith('### ')) return <Text key={key} style={styles.mdH3}>{line.substring(4)}</Text>;
      if (line.startsWith('- ')) return (
        <View key={key} style={styles.mdListItem}>
          <Text style={styles.mdBullet}>•</Text>
          {renderInline(line.substring(2), styles.mdText, `${key}-li`)}
        </View>
      );
      if (line.startsWith('| ')) return <Text key={key} style={styles.mdTableRow}>{line}</Text>;
      if (line.startsWith('---')) return <View key={key} style={styles.mdDivider} />;
      if (line.trim() === '' || line.trim() === '*') return <View key={key} style={{ height: 8 }} />;
      return renderInline(line, styles.mdText, key);
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
          {/* Back Button */}
          <View style={styles.signedHeader}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
              <Ionicons name="chevron-back" size={28} color="#007AFF" />
            </TouchableOpacity>
            <Text style={styles.signedHeaderTitle}>Agreement Details</Text>
            <View style={{ width: 28 }} />
          </View>
          <ScrollView contentContainerStyle={styles.signedContent}>
            <View style={styles.successBadge}>
              <Ionicons name="checkmark-circle" size={80} color="#34C759" />
            </View>
            <Text style={styles.signedTitle}>Agreement Signed!</Text>
            <Text style={styles.signedSubtitle}>
              Welcome to the Partner Program — {agreement.template_name}
            </Text>
            
            <View style={styles.signedDetails}>
              <View style={styles.signedDetailRow}>
                <Text style={styles.signedDetailLabel}>Partner</Text>
                <Text style={styles.signedDetailValue}>{agreement.signed_partner?.name}</Text>
              </View>
              <View style={styles.signedDetailRow}>
                <Text style={styles.signedDetailLabel}>Agreement Type</Text>
                <Text style={styles.signedDetailValue}>{agreement.template_name}</Text>
              </View>
              {agreement.commission_tier && (
                <View style={styles.signedDetailRow}>
                  <Text style={styles.signedDetailLabel}>Commission</Text>
                  <Text style={styles.signedDetailValue}>
                    {agreement.custom_commission_notes
                      ? agreement.custom_commission_notes
                      : `Per Exhibit A — ${agreement.type === 'reseller' ? '20/30/40%' : '10/15%'} tiers`}
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

            {/* W-9 Section */}
            <View style={[styles.signedDetails, { marginTop: 20, borderTopWidth: 1, borderTopColor: '#E5E5EA', paddingTop: 20 }]}>
              <Text style={[styles.signedTitle, { fontSize: 18, marginBottom: 6 }]}>Next Step: Submit Your W-9</Text>
              <Text style={{ fontSize: 14, color: '#636366', textAlign: 'center', marginBottom: 16, lineHeight: 20 }}>
                A W-9 is required to receive commission payments.
              </Text>

              {/* Already submitted */}
              {(w9Uploaded || agreement.w9_status === 'uploaded' || agreement.w9_status === 'verified') ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F0FFF4', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#34C759' }}>
                  <Ionicons name="checkmark-circle" size={24} color="#34C759" />
                  <Text style={{ fontSize: 15, fontWeight: '600', color: '#34C759' }}>
                    W-9 {agreement.w9_status === 'verified' ? 'Verified ✓' : 'Submitted — pending review'}
                  </Text>
                </View>
              ) : w9Mode === 'choose' ? (
                /* Two-option chooser */
                <View style={{ gap: 12 }}>
                  {/* Digital form option */}
                  <TouchableOpacity
                    onPress={() => { setW9Form(f => ({ ...f, legal_name: agreement.signed_partner?.name || '', signature: agreement.signed_partner?.name || '' })); setW9Mode('digital'); }}
                    style={{ backgroundColor: '#007AFF', borderRadius: 14, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 14 }}
                    data-testid="w9-digital-btn"
                  >
                    <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.2)', alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name="document-text" size={22} color="#fff" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 16, fontWeight: '700', color: '#fff' }}>Fill Out W-9 Digitally</Text>
                      <Text style={{ fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 2 }}>Complete the form in-app — takes 2 minutes</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color="rgba(255,255,255,0.7)" />
                  </TouchableOpacity>

                  {/* Upload / photo option */}
                  <TouchableOpacity
                    onPress={() => setW9Mode('upload')}
                    style={{ backgroundColor: '#1C1C1E', borderRadius: 14, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 14 }}
                    data-testid="w9-upload-btn"
                  >
                    <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.1)', alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name="camera" size={22} color="#fff" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 16, fontWeight: '700', color: '#fff' }}>Upload or Photograph W-9</Text>
                      <Text style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)', marginTop: 2 }}>Snap a photo or upload a PDF / image</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color="rgba(255,255,255,0.4)" />
                  </TouchableOpacity>
                </View>

              ) : w9Mode === 'upload' ? (
                /* Upload / camera chooser */
                <View style={{ gap: 10 }}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: '#1C1C1E', marginBottom: 4 }}>How do you want to submit?</Text>
                  {Platform.OS !== 'web' && (
                    <TouchableOpacity
                      style={{ backgroundColor: '#34C759', borderRadius: 14, padding: 15, flexDirection: 'row', alignItems: 'center', gap: 10, opacity: w9Uploading ? 0.6 : 1 }}
                      onPress={() => handleW9Upload(true)}
                      disabled={w9Uploading}
                    >
                      {w9Uploading ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="camera" size={20} color="#fff" />}
                      <Text style={{ fontSize: 15, fontWeight: '700', color: '#fff' }}>Take a Photo of My W-9</Text>
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity
                    style={{ backgroundColor: '#007AFF', borderRadius: 14, padding: 15, flexDirection: 'row', alignItems: 'center', gap: 10, opacity: w9Uploading ? 0.6 : 1 }}
                    onPress={() => handleW9Upload(false)}
                    disabled={w9Uploading}
                  >
                    {w9Uploading ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="cloud-upload" size={20} color="#fff" />}
                    <Text style={{ fontSize: 15, fontWeight: '700', color: '#fff' }}>Upload PDF or Image</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => setW9Mode('choose')}>
                    <Text style={{ fontSize: 14, color: '#636366', textAlign: 'center', marginTop: 4 }}>← Back</Text>
                  </TouchableOpacity>
                </View>

              ) : (
                /* Digital W-9 form */
                <View>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: '#1C1C1E', marginBottom: 14 }}>W-9 Tax Information</Text>

                  {[
                    { key: 'legal_name',   label: 'Legal Name (as on tax return) *', placeholder: 'Your full legal name' },
                    { key: 'business_name',label: 'Business Name (if different)', placeholder: 'Optional — LLC name, DBA, etc.' },
                    { key: 'address',      label: 'Street Address *', placeholder: '123 Main St' },
                    { key: 'city_state_zip',label: 'City, State, ZIP *', placeholder: 'Salt Lake City, UT 84101' },
                  ].map(f => (
                    <View key={f.key} style={{ marginBottom: 12 }}>
                      <Text style={{ fontSize: 12, fontWeight: '600', color: '#636366', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 }}>{f.label}</Text>
                      <TextInput
                        style={{ backgroundColor: '#F2F2F7', borderRadius: 10, padding: 13, fontSize: 15, color: '#1C1C1E' }}
                        value={(w9Form as any)[f.key]}
                        onChangeText={v => setW9Form(p => ({ ...p, [f.key]: v }))}
                        placeholder={f.placeholder}
                        placeholderTextColor="#8E8E93"
                        autoCapitalize={f.key === 'legal_name' || f.key === 'business_name' ? 'words' : 'sentences'}
                      />
                    </View>
                  ))}

                  {/* Tax classification */}
                  <Text style={{ fontSize: 12, fontWeight: '600', color: '#636366', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>Federal Tax Classification *</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                    {TAX_CLASSES.map(tc => (
                      <TouchableOpacity
                        key={tc.key}
                        onPress={() => setW9Form(p => ({ ...p, tax_classification: tc.key }))}
                        style={{ paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20, borderWidth: 1.5,
                          borderColor: w9Form.tax_classification === tc.key ? '#007AFF' : '#E5E5EA',
                          backgroundColor: w9Form.tax_classification === tc.key ? '#007AFF15' : '#F9F9F9' }}
                      >
                        <Text style={{ fontSize: 13, fontWeight: '600', color: w9Form.tax_classification === tc.key ? '#007AFF' : '#3C3C43' }}>
                          {tc.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  {/* TIN */}
                  <Text style={{ fontSize: 12, fontWeight: '600', color: '#636366', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 }}>SSN or EIN *</Text>
                  <TextInput
                    style={{ backgroundColor: '#FFF9E6', borderRadius: 10, padding: 13, fontSize: 16, color: '#1C1C1E', borderWidth: 1, borderColor: '#FFD60A', marginBottom: 12, fontFamily: 'monospace' }}
                    value={w9Form.tin}
                    onChangeText={v => setW9Form(p => ({ ...p, tin: v.replace(/[^\d-]/g, '') }))}
                    placeholder="XXX-XX-XXXX or XX-XXXXXXX"
                    placeholderTextColor="#8E8E93"
                    keyboardType="numeric"
                    secureTextEntry={false}
                    maxLength={11}
                  />
                  <Text style={{ fontSize: 11, color: '#8E8E93', marginBottom: 14, lineHeight: 16 }}>
                    Your TIN is encrypted and only used for tax reporting purposes. We never store it in plain text.
                  </Text>

                  {/* Signature */}
                  <Text style={{ fontSize: 12, fontWeight: '600', color: '#636366', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 }}>Signature (type to certify) *</Text>
                  <TextInput
                    style={{ backgroundColor: '#F2F2F7', borderRadius: 10, padding: 13, fontSize: 18, color: '#1C1C1E', fontStyle: 'italic', marginBottom: 8 }}
                    value={w9Form.signature}
                    onChangeText={v => setW9Form(p => ({ ...p, signature: v }))}
                    placeholder="Type your full legal name"
                    placeholderTextColor="#8E8E93"
                    autoCapitalize="words"
                  />
                  <Text style={{ fontSize: 12, color: '#636366', marginBottom: 16, lineHeight: 17 }}>
                    By typing my name above, I certify under penalties of perjury that the information on this form is correct and that I am a U.S. person.
                  </Text>

                  <TouchableOpacity
                    style={{ backgroundColor: '#007AFF', borderRadius: 14, padding: 16, alignItems: 'center', opacity: w9Uploading ? 0.6 : 1 }}
                    onPress={handleW9Digital}
                    disabled={w9Uploading}
                    data-testid="w9-submit-btn"
                  >
                    {w9Uploading ? <ActivityIndicator color="#fff" /> : <Text style={{ fontSize: 17, fontWeight: '800', color: '#fff' }}>Submit W-9</Text>}
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => setW9Mode('choose')} style={{ marginTop: 12 }}>
                    <Text style={{ fontSize: 14, color: '#636366', textAlign: 'center' }}>← Back</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
            
            <Text style={styles.nextStepsTitle}>What's Next?</Text>
            <View style={styles.nextStep}>
              <Ionicons name="mail-outline" size={24} color="#007AFF" />
              <Text style={styles.nextStepText}>You'll receive a welcome email with your partner portal access</Text>
            </View>
            <View style={styles.nextStep}>
              <Ionicons name="link-outline" size={24} color="#007AFF" />
              <Text style={styles.nextStepText}>Your unique referral link will be activated within 24 hours</Text>
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
          {/* Back Button */}
          <View style={styles.paymentHeader}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
              <Ionicons name="chevron-back" size={28} color="#007AFF" />
            </TouchableOpacity>
            <Text style={styles.paymentHeaderTitle}>Complete Payment</Text>
            <View style={{ width: 28 }} />
          </View>
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
        {/* Header with Back Button */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <View style={styles.headerContent}>
            <Text style={styles.headerTitle}>{agreement.template_name}</Text>
            {(() => {
              // Resolve the best commission display string
              let displayPct = '';
              // 1. Explicit percentage on commission_tier object
              if (agreement.commission_tier?.percentage) {
                displayPct = `${agreement.commission_tier.percentage}%`;
              }
              // 2. Parse from custom_commission_notes (e.g. "50% commission")
              if (!displayPct && agreement.custom_commission_notes) {
                const match = agreement.custom_commission_notes.match(/(\d+(?:\.\d+)?)\s*%/);
                if (match) displayPct = `${match[1]}%`;
              }
              // 3. Standard tier fallback
              if (!displayPct) {
                displayPct = agreement.type === 'reseller' ? '20/30/40%' : '10/15%';
              }
              return (
                <View style={styles.tierBadge}>
                  <Text style={styles.tierBadgeText}>{displayPct}</Text>
                </View>
              );
            })()}
          </View>
          <View style={{ width: 28 }} />
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
                I have read and agree to the{' '}
                <Text
                  style={{ color: '#007AFF', textDecorationLine: 'underline' }}
                  onPress={(e) => {
                    e.stopPropagation?.();
                    if (typeof window !== 'undefined') window.open('https://imonsocial.com/terms', '_blank');
                  }}
                >
                  Terms of Service
                </Text>
                {' '}and{' '}
                <Text
                  style={{ color: '#007AFF', textDecorationLine: 'underline' }}
                  onPress={(e) => {
                    e.stopPropagation?.();
                    if (typeof window !== 'undefined') window.open('https://imonsocial.com/privacy', '_blank');
                  }}
                >
                  Privacy Policy
                </Text>
                {' '}of this agreement.
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
    fontSize: 18,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  errorTitle: {
    fontSize: 21,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  errorText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  signedContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  signedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  signedHeaderTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 19,
    fontWeight: '600',
    color: '#FFF',
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
    fontSize: 18,
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
    fontSize: 16,
    color: '#8E8E93',
  },
  signedDetailValue: {
    fontSize: 16,
    color: '#FFF',
    fontWeight: '600',
  },
  nextStepsTitle: {
    fontSize: 19,
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
    fontSize: 16,
    color: '#FFF',
    marginLeft: 12,
  },
  paymentContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  paymentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  paymentHeaderTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 19,
    fontWeight: '600',
    color: '#FFF',
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
    fontSize: 18,
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
    fontSize: 16,
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
    fontSize: 19,
    fontWeight: '600',
    color: '#FFF',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    paddingTop: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerContent: {
    flex: 1,
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 19,
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
    fontSize: 16,
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
    fontSize: 19,
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
    fontSize: 22,
    fontWeight: '800',
    color: '#FFF',
    marginBottom: 14,
    marginTop: 8,
  },
  mdH2: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
    marginTop: 20,
    marginBottom: 10,
  },
  mdH3: {
    fontSize: 16,
    fontWeight: '700',
    color: '#E5E5EA',
    marginTop: 14,
    marginBottom: 8,
  },
  mdBold: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFF',
  },
  mdTableRow: {
    fontSize: 14,
    color: '#CCC',
    fontFamily: 'monospace',
    lineHeight: 22,
    paddingVertical: 2,
  },
  mdText: {
    fontSize: 16,
    color: '#CCC',
    lineHeight: 22,
  },
  mdListItem: {
    flexDirection: 'row',
    paddingLeft: 8,
    marginBottom: 8,
  },
  mdBullet: {
    fontSize: 16,
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
    fontSize: 16,
    color: '#8E8E93',
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
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
    fontSize: 16,
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
    fontSize: 18,
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
    fontSize: 16,
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
    fontSize: 15,
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
    fontSize: 19,
    fontWeight: '600',
    color: '#FFF',
  },
});
