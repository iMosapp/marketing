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
  Modal,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { Picker } from '@react-native-picker/picker';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
const DISCOUNT_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50];
const BUSINESS_TYPES = ['LLC', 'Corporation', 'Partnership', 'Sole Proprietor', 'Non-Profit', 'Other'];
const INDUSTRY_VERTICALS = [
  'Automotive',
  'Real Estate', 
  'Insurance',
  'Financial Services',
  'Healthcare',
  'Retail',
  'Professional Services',
  'Other'
];

export default function CreateQuotePage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  
  // Plan selection
  const [planType, setPlanType] = useState<'individual' | 'store'>('individual');
  const [selectedPlan, setSelectedPlan] = useState('monthly');
  const [numUsers, setNumUsers] = useState(5);
  
  // Customer info
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerTitle, setCustomerTitle] = useState('');
  
  // Business info (for store/10DLC)
  const [companyName, setCompanyName] = useState('');
  const [website, setWebsite] = useState('');
  const [streetAddress, setStreetAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zipCode, setZipCode] = useState('');
  const [ein, setEin] = useState('');
  const [businessType, setBusinessType] = useState('');
  const [w9Required, setW9Required] = useState(true);
  
  // Authorized signer
  const [signerName, setSignerName] = useState('');
  const [signerTitle, setSignerTitle] = useState('');
  const [signerEmail, setSignerEmail] = useState('');
  const [signerPhone, setSignerPhone] = useState('');
  
  // 10DLC Info
  const [brandName, setBrandName] = useState('');
  const [vertical, setVertical] = useState('');
  
  // Discount
  const [discountPercent, setDiscountPercent] = useState(0);
  const [discountCode, setDiscountCode] = useState('');
  const [validatedDiscount, setValidatedDiscount] = useState<number | null>(null);
  
  // Quote preparer
  const [preparedByName, setPreparedByName] = useState('');
  const [notes, setNotes] = useState('');
  
  // UI State
  const [loading, setLoading] = useState(false);
  const [calculatedPrice, setCalculatedPrice] = useState(0);
  const [showDiscountModal, setShowDiscountModal] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [createdQuoteNumber, setCreatedQuoteNumber] = useState('');
  
  useEffect(() => {
    if (user) {
      setPreparedByName(user.name || '');
    }
    calculatePrice();
  }, [user]);
  
  useEffect(() => {
    calculatePrice();
  }, [planType, selectedPlan, numUsers, discountPercent, validatedDiscount]);
  
  const calculatePrice = async () => {
    let basePrice = 0;
    
    if (planType === 'store') {
      try {
        const response = await api.get(`/subscriptions/plans/store/calculate?num_users=${numUsers}`);
        if (!response.data.error) {
          basePrice = response.data.total_monthly;
        }
      } catch (error) {
        basePrice = numUsers >= 6 ? numUsers * 65 : numUsers * 75;
      }
    } else {
      switch (selectedPlan) {
        case 'monthly': basePrice = 100; break;
        case 'annual': basePrice = 1000; break;
        case 'intro': basePrice = 50; break;
        default: basePrice = 100;
      }
    }
    
    const discount = validatedDiscount || discountPercent;
    const finalPrice = basePrice - (basePrice * discount / 100);
    setCalculatedPrice(finalPrice);
  };
  
  const validateDiscountCode = async () => {
    if (!discountCode) return;
    
    try {
      const response = await api.get(`/subscriptions/discount-codes/validate/${discountCode}?plan_type=${planType}`);
      if (response.data.valid) {
        setValidatedDiscount(response.data.discount_percent);
        showSimpleAlert('Success', `Discount code applied: ${response.data.discount_percent}% off`);
      } else {
        showSimpleAlert('Invalid Code', response.data.message);
        setValidatedDiscount(null);
      }
    } catch (error) {
      showSimpleAlert('Error', 'Failed to validate code');
    }
  };
  
  const handleCreateQuote = async () => {
    if (!customerEmail && !companyName) {
      showSimpleAlert('Error', 'Please enter customer email or company name');
      return;
    }
    
    if (planType === 'store' && !companyName) {
      showSimpleAlert('Error', 'Company name is required for store plans');
      return;
    }
    
    setLoading(true);
    
    try {
      const quoteData = {
        plan_type: planType,
        plan_id: planType === 'individual' ? selectedPlan : 'store',
        num_users: planType === 'store' ? numUsers : 1,
        
        // Customer
        email: customerEmail,
        name: customerName,
        phone: customerPhone,
        title: customerTitle,
        
        // Business
        company_name: companyName,
        website: website,
        street_address: streetAddress,
        city: city,
        state: state,
        zip_code: zipCode,
        ein: ein,
        business_type: businessType,
        w9_required: w9Required,
        
        // Signer
        signer_name: signerName || customerName,
        signer_title: signerTitle || customerTitle,
        signer_email: signerEmail || customerEmail,
        signer_phone: signerPhone || customerPhone,
        
        // 10DLC
        brand_name: brandName || companyName,
        vertical: vertical,
        
        // Discount
        discount_percent: validatedDiscount || discountPercent,
        discount_code: validatedDiscount ? discountCode : '',
        
        // Preparer
        prepared_by_name: preparedByName,
        prepared_by_email: user?.email || '',
        notes: notes,
      };
      
      const response = await api.post('/subscriptions/quotes', quoteData);
      
      // Show success modal
      setCreatedQuoteNumber(response.data.quote_number);
      setShowSuccessModal(true);
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to create quote');
    } finally {
      setLoading(false);
    }
  };
  
  const resetForm = () => {
    setCustomerName('');
    setCustomerEmail('');
    setCustomerPhone('');
    setCustomerTitle('');
    setCompanyName('');
    setWebsite('');
    setStreetAddress('');
    setCity('');
    setState('');
    setZipCode('');
    setEin('');
    setBusinessType('');
    setSignerName('');
    setSignerTitle('');
    setSignerEmail('');
    setSignerPhone('');
    setBrandName('');
    setVertical('');
    setDiscountPercent(0);
    setDiscountCode('');
    setValidatedDiscount(null);
    setNotes('');
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Create Quote</Text>
        <View style={{ width: 40 }} />
      </View>
      
      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Plan Type Selection */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Plan Type</Text>
          <View style={styles.tabContainer}>
            <TouchableOpacity
              style={[styles.tab, planType === 'individual' && styles.tabActive]}
              onPress={() => setPlanType('individual')}
            >
              <Ionicons name="person" size={20} color={planType === 'individual' ? '#FFF' : colors.textSecondary} />
              <Text style={[styles.tabText, planType === 'individual' && styles.tabTextActive]}>Individual</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, planType === 'store' && styles.tabActive]}
              onPress={() => setPlanType('store')}
            >
              <Ionicons name="storefront" size={20} color={planType === 'store' ? '#FFF' : colors.textSecondary} />
              <Text style={[styles.tabText, planType === 'store' && styles.tabTextActive]}>Account / Team</Text>
            </TouchableOpacity>
          </View>
        </View>
        
        {/* Plan Selection (Individual) */}
        {planType === 'individual' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Select Plan</Text>
            <View style={styles.planOptions}>
              {[
                { id: 'monthly', name: 'Monthly', price: '$100/mo' },
                { id: 'annual', name: 'Annual', price: '$1000/yr' },
                { id: 'intro', name: 'Intro Offer', price: '$50/mo (3mo)' },
              ].map((plan) => (
                <TouchableOpacity
                  key={plan.id}
                  style={[styles.planOption, selectedPlan === plan.id && styles.planOptionActive]}
                  onPress={() => setSelectedPlan(plan.id)}
                >
                  <Text style={[styles.planOptionName, selectedPlan === plan.id && styles.planOptionNameActive]}>
                    {plan.name}
                  </Text>
                  <Text style={[styles.planOptionPrice, selectedPlan === plan.id && styles.planOptionPriceActive]}>
                    {plan.price}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}
        
        {/* User Count (Store) */}
        {planType === 'store' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Number of Users</Text>
            <View style={styles.userCountRow}>
              <TouchableOpacity
                style={styles.userCountButton}
                onPress={() => setNumUsers(Math.max(5, numUsers - 1))}
              >
                <Ionicons name="remove" size={24} color={colors.text} />
              </TouchableOpacity>
              <View style={styles.userCountDisplay}>
                <Text style={styles.userCountNumber}>{numUsers}</Text>
                <Text style={styles.userCountLabel}>users</Text>
              </View>
              <TouchableOpacity
                style={styles.userCountButton}
                onPress={() => setNumUsers(numUsers + 1)}
              >
                <Ionicons name="add" size={24} color={colors.text} />
              </TouchableOpacity>
            </View>
            <Text style={styles.userPriceNote}>
              {numUsers >= 6 ? '$65/user (volume discount)' : '$75/user'} = ${numUsers >= 6 ? numUsers * 65 : numUsers * 75}/mo
            </Text>
          </View>
        )}
        
        {/* Discount Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Discount</Text>
          <Text style={styles.discountSubtitle}>for first 90 days</Text>
          <ScrollView 
            horizontal 
            showsHorizontalScrollIndicator={false}
            style={styles.discountSlider}
            contentContainerStyle={styles.discountSliderContent}
          >
            {DISCOUNT_OPTIONS.map((pct) => (
              <TouchableOpacity
                key={pct}
                style={[styles.discountTile, discountPercent === pct && !validatedDiscount && styles.discountTileActive]}
                onPress={() => { setDiscountPercent(pct); setValidatedDiscount(null); setDiscountCode(''); }}
                disabled={!!validatedDiscount}
              >
                <Text style={[styles.discountTileText, discountPercent === pct && !validatedDiscount && styles.discountTileTextActive]}>
                  {pct}%
                </Text>
                {pct > 0 && <Text style={[styles.discountTileLabel, discountPercent === pct && !validatedDiscount && styles.discountTileLabelActive]}>OFF</Text>}
              </TouchableOpacity>
            ))}
          </ScrollView>
          
          <View style={styles.discountCodeRow}>
            <TextInput
              style={styles.discountCodeInput}
              placeholder="Or enter discount code"
              placeholderTextColor={colors.textSecondary}
              value={discountCode}
              onChangeText={setDiscountCode}
              autoCapitalize="characters"
            />
            <TouchableOpacity style={styles.applyButton} onPress={validateDiscountCode}>
              <Text style={styles.applyButtonText}>Apply</Text>
            </TouchableOpacity>
          </View>
          
          {validatedDiscount && (
            <View style={styles.appliedDiscount}>
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
              <Text style={styles.appliedDiscountText}>
                Code applied: {validatedDiscount}% off
              </Text>
              <TouchableOpacity onPress={() => { setValidatedDiscount(null); setDiscountCode(''); }}>
                <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
          )}
        </View>
        
        {/* Price Summary */}
        <View style={styles.priceSummary}>
          <Text style={styles.priceSummaryLabel}>Quote Total:</Text>
          <Text style={styles.priceSummaryAmount}>${calculatedPrice.toFixed(2)}</Text>
          <Text style={styles.priceSummaryInterval}>
            /{planType === 'store' || selectedPlan !== 'annual' ? 'month' : 'year'}
          </Text>
        </View>
        
        {/* Customer Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Customer Contact</Text>
          <TextInput
            style={styles.input}
            placeholder="Contact Name *"
            placeholderTextColor={colors.textSecondary}
            value={customerName}
            onChangeText={setCustomerName}
          />
          <TextInput
            style={styles.input}
            placeholder="Email *"
            placeholderTextColor={colors.textSecondary}
            value={customerEmail}
            onChangeText={setCustomerEmail}
            keyboardType="email-address"
            autoCapitalize="none"
          />
          <TextInput
            style={styles.input}
            placeholder="Phone"
            placeholderTextColor={colors.textSecondary}
            value={customerPhone}
            onChangeText={setCustomerPhone}
            keyboardType="phone-pad"
          />
          <TextInput
            style={styles.input}
            placeholder="Title/Position"
            placeholderTextColor={colors.textSecondary}
            value={customerTitle}
            onChangeText={setCustomerTitle}
          />
        </View>
        
        {/* Business Info (Store Plans) */}
        {planType === 'store' && (
          <>
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Business Information</Text>
              <Text style={styles.sectionNote}>Required for 10DLC SMS compliance</Text>
              
              <TextInput
                style={styles.input}
                placeholder="Company Name *"
                placeholderTextColor={colors.textSecondary}
                value={companyName}
                onChangeText={setCompanyName}
              />
              <TextInput
                style={styles.input}
                placeholder="Website URL"
                placeholderTextColor={colors.textSecondary}
                value={website}
                onChangeText={setWebsite}
                keyboardType="url"
                autoCapitalize="none"
              />
              <TextInput
                style={styles.input}
                placeholder="Street Address"
                placeholderTextColor={colors.textSecondary}
                value={streetAddress}
                onChangeText={setStreetAddress}
              />
              <View style={styles.inputRow}>
                <TextInput
                  style={[styles.input, styles.inputHalf]}
                  placeholder="City"
                  placeholderTextColor={colors.textSecondary}
                  value={city}
                  onChangeText={setCity}
                />
                <TextInput
                  style={[styles.input, styles.inputQuarter]}
                  placeholder="State"
                  placeholderTextColor={colors.textSecondary}
                  value={state}
                  onChangeText={setState}
                  maxLength={2}
                  autoCapitalize="characters"
                />
                <TextInput
                  style={[styles.input, styles.inputQuarter]}
                  placeholder="ZIP"
                  placeholderTextColor={colors.textSecondary}
                  value={zipCode}
                  onChangeText={setZipCode}
                  keyboardType="number-pad"
                  maxLength={5}
                />
              </View>
              <TextInput
                style={styles.input}
                placeholder="EIN (Tax ID)"
                placeholderTextColor={colors.textSecondary}
                value={ein}
                onChangeText={setEin}
              />
              
              <Text style={styles.inputLabel}>Business Type</Text>
              <View style={styles.selectContainer}>
                <Picker
                  selectedValue={businessType}
                  onValueChange={setBusinessType}
                  style={styles.picker}
                  dropdownIconColor={colors.textSecondary}
                >
                  <Picker.Item label="Select business type..." value="" />
                  {BUSINESS_TYPES.map((type) => (
                    <Picker.Item key={type} label={type} value={type} />
                  ))}
                </Picker>
              </View>
              
              <Text style={styles.inputLabel}>Industry Vertical</Text>
              <View style={styles.selectContainer}>
                <Picker
                  selectedValue={vertical}
                  onValueChange={setVertical}
                  style={styles.picker}
                  dropdownIconColor={colors.textSecondary}
                >
                  <Picker.Item label="Select industry..." value="" />
                  {INDUSTRY_VERTICALS.map((v) => (
                    <Picker.Item key={v} label={v} value={v} />
                  ))}
                </Picker>
              </View>
              
              <View style={styles.switchRow}>
                <Text style={styles.switchLabel}>W-9 Required</Text>
                <Switch
                  value={w9Required}
                  onValueChange={setW9Required}
                  trackColor={{ false: colors.surface, true: '#007AFF' }}
                />
              </View>
            </View>
            
            {/* Authorized Signer */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Authorized Signer</Text>
              <Text style={styles.sectionNote}>Person authorized to sign contracts</Text>
              
              <TextInput
                style={styles.input}
                placeholder="Signer Name (if different)"
                placeholderTextColor={colors.textSecondary}
                value={signerName}
                onChangeText={setSignerName}
              />
              <TextInput
                style={styles.input}
                placeholder="Signer Title"
                placeholderTextColor={colors.textSecondary}
                value={signerTitle}
                onChangeText={setSignerTitle}
              />
              <TextInput
                style={styles.input}
                placeholder="Signer Email"
                placeholderTextColor={colors.textSecondary}
                value={signerEmail}
                onChangeText={setSignerEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />
              <TextInput
                style={styles.input}
                placeholder="Signer Phone"
                placeholderTextColor={colors.textSecondary}
                value={signerPhone}
                onChangeText={setSignerPhone}
                keyboardType="phone-pad"
              />
            </View>
          </>
        )}
        
        {/* Quote Preparer */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quote Prepared By</Text>
          <TextInput
            style={styles.input}
            placeholder="Your Name"
            placeholderTextColor={colors.textSecondary}
            value={preparedByName}
            onChangeText={setPreparedByName}
          />
          <TextInput
            style={[styles.input, styles.textArea]}
            placeholder="Notes or special terms..."
            placeholderTextColor={colors.textSecondary}
            value={notes}
            onChangeText={setNotes}
            multiline
            numberOfLines={4}
          />
        </View>
        
        {/* Create Button */}
        <TouchableOpacity
          style={[styles.createButton, loading && styles.createButtonDisabled]}
          onPress={handleCreateQuote}
          disabled={loading}
          data-testid="create-quote-button"
        >
          {loading ? (
            <ActivityIndicator color={colors.text} />
          ) : (
            <>
              <Ionicons name="document-text" size={24} color={colors.text} />
              <Text style={styles.createButtonText}>Create Quote</Text>
            </>
          )}
        </TouchableOpacity>
        
        <View style={{ height: 40 }} />
      </ScrollView>
      
      {/* Success Modal */}
      <Modal
        visible={showSuccessModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowSuccessModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.successModal}>
            <View style={styles.successIconContainer}>
              <Ionicons name="checkmark-circle" size={64} color="#34C759" />
            </View>
            <Text style={styles.successTitle}>Quote Created!</Text>
            <Text style={styles.successMessage}>
              Quote <Text style={styles.quoteNumber}>{createdQuoteNumber}</Text> has been created successfully.
            </Text>
            <View style={styles.successButtons}>
              <TouchableOpacity
                style={styles.successButtonSecondary}
                onPress={() => {
                  setShowSuccessModal(false);
                  resetForm();
                }}
              >
                <Ionicons name="add" size={20} color="#007AFF" />
                <Text style={styles.successButtonSecondaryText}>Create Another</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.successButtonPrimary}
                onPress={() => {
                  setShowSuccessModal(false);
                  router.push('/admin/quotes');
                }}
              >
                <Ionicons name="list" size={20} color={colors.text} />
                <Text style={styles.successButtonPrimaryText}>View Quotes</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
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
    width: 40,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
  },
  section: {
    marginTop: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 12,
  },
  sectionNote: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: -8,
    marginBottom: 12,
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 4,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 6,
  },
  tabActive: {
    backgroundColor: '#007AFF',
  },
  tabText: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  tabTextActive: {
    color: colors.text,
  },
  planOptions: {
    gap: 8,
  },
  planOption: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  planOptionActive: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF20',
  },
  planOptionName: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.text,
  },
  planOptionNameActive: {
    color: '#007AFF',
  },
  planOptionPrice: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  planOptionPriceActive: {
    color: '#007AFF',
  },
  userCountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 24,
  },
  userCountButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  userCountDisplay: {
    alignItems: 'center',
    minWidth: 60,
  },
  userCountNumber: {
    fontSize: 40,
    fontWeight: '700',
    color: colors.text,
  },
  userCountLabel: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  userPriceNote: {
    textAlign: 'center',
    fontSize: 14,
    color: '#34C759',
    marginTop: 12,
  },
  discountSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 12,
  },
  discountSlider: {
    marginBottom: 16,
    marginHorizontal: -16,
  },
  discountSliderContent: {
    paddingHorizontal: 16,
    gap: 10,
  },
  discountTile: {
    minWidth: 72,
    paddingVertical: 16,
    paddingHorizontal: 20,
    backgroundColor: colors.card,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.surface,
  },
  discountTileActive: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF15',
  },
  discountTileText: {
    fontSize: 22,
    color: colors.text,
    fontWeight: '700',
  },
  discountTileTextActive: {
    color: '#007AFF',
  },
  discountTileLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '600',
    marginTop: 2,
  },
  discountTileLabelActive: {
    color: '#007AFF',
  },
  discountCodeRow: {
    flexDirection: 'row',
    gap: 8,
  },
  discountCodeInput: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  applyButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    paddingHorizontal: 20,
    justifyContent: 'center',
  },
  applyButtonText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  appliedDiscount: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#34C75920',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
  },
  appliedDiscountText: {
    flex: 1,
    fontSize: 14,
    color: '#34C759',
    fontWeight: '500',
  },
  priceSummary: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'center',
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 20,
    marginTop: 24,
  },
  priceSummaryLabel: {
    fontSize: 16,
    color: colors.textSecondary,
    marginRight: 8,
  },
  priceSummaryAmount: {
    fontSize: 36,
    fontWeight: '700',
    color: '#34C759',
  },
  priceSummaryInterval: {
    fontSize: 18,
    color: colors.textSecondary,
    marginLeft: 4,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: colors.text,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  inputRow: {
    flexDirection: 'row',
    gap: 8,
  },
  inputHalf: {
    flex: 2,
  },
  inputQuarter: {
    flex: 1,
  },
  inputLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 8,
    marginTop: 4,
  },
  selectContainer: {
    backgroundColor: colors.card,
    borderRadius: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  picker: {
    color: colors.text,
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    marginTop: 8,
  },
  switchLabel: {
    fontSize: 16,
    color: colors.text,
  },
  textArea: {
    minHeight: 100,
    textAlignVertical: 'top',
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    marginTop: 24,
    gap: 8,
  },
  createButtonDisabled: {
    opacity: 0.6,
  },
  createButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  // Success Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  successModal: {
    backgroundColor: colors.card,
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 400,
    alignItems: 'center',
  },
  successIconContainer: {
    marginBottom: 16,
  },
  successTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  successMessage: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 24,
  },
  quoteNumber: {
    color: '#007AFF',
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  successButtons: {
    flexDirection: 'row',
    gap: 12,
    width: '100%',
  },
  successButtonPrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#007AFF',
    borderRadius: 12,
    paddingVertical: 14,
  },
  successButtonPrimaryText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  successButtonSecondary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingVertical: 14,
  },
  successButtonSecondaryText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
});
