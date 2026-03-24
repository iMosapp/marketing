import React, { useState, useEffect } from 'react';
import { showAlert } from '../../services/alert';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  Linking,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
interface Plan {
  id: string;
  name: string;
  type?: string;
  price?: number;
  price_per_user?: number;
  min_users?: number;
  interval: string;
  trial_days: number;
  description: string;
  features: string[];
  badge?: string;
  original_price?: number;
  original_price_per_user?: number;
  discount_percent?: number;
  terms?: string;
}

export default function PricingPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const [individualPlans, setIndividualPlans] = useState<Plan[]>([]);
  const [storePlans, setStorePlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingPlan, setProcessingPlan] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'individual' | 'store'>('individual');
  const [userCount, setUserCount] = useState(5);
  const [storeTotal, setStoreTotal] = useState<number>(0);
  const [storePricePerUser, setStorePricePerUser] = useState<number>(75);

  useEffect(() => {
    loadPlans();
  }, []);

  useEffect(() => {
    calculateStorePrice();
  }, [userCount]);

  const loadPlans = async () => {
    try {
      const response = await api.get('/subscriptions/plans');
      const allPlans = response.data.plans;
      setIndividualPlans(allPlans.filter((p: Plan) => p.type !== 'store'));
      setStorePlans(allPlans.filter((p: Plan) => p.type === 'store'));
      calculateStorePrice();
    } catch (error) {
      console.error('Error loading plans:', error);
      showAlert('Error', 'Failed to load pricing plans');
    } finally {
      setLoading(false);
    }
  };

  const calculateStorePrice = async () => {
    try {
      const response = await api.get(`/subscriptions/plans/store/calculate?num_users=${userCount}`);
      if (!response.data.error) {
        setStoreTotal(response.data.total_monthly);
        setStorePricePerUser(response.data.price_per_user);
      }
    } catch (error) {
      console.error('Error calculating store price:', error);
    }
  };

  const handleSelectPlan = async (plan: Plan, numUsers?: number) => {
    const planId = plan.type === 'store' 
      ? (userCount >= 6 ? 'store_volume' : 'store_standard')
      : plan.id;
    
    setProcessingPlan(planId);
    
    try {
      const originUrl = typeof window !== 'undefined' 
        ? (process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com')
        : 'https://app.imonsocial.com';
      
      const checkoutData: any = {
        plan_id: planId,
        origin_url: originUrl,
      };
      
      if (plan.type === 'store') {
        checkoutData.num_users = userCount;
      }
      
      const response = await api.post('/subscriptions/checkout', checkoutData);
      
      if (response.data.url) {
        if (typeof window !== 'undefined') {
          window.location.href = response.data.url;
        } else {
          await Linking.openURL(response.data.url);
        }
      }
    } catch (error: any) {
      console.error('Checkout error:', error);
      showAlert('Error', error.response?.data?.detail || 'Failed to start checkout');
    } finally {
      setProcessingPlan(null);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  const renderIndividualPlans = () => (
    <>
      {individualPlans.map((plan) => (
        <TouchableOpacity
          key={plan.id}
          style={[
            styles.planCard,
            plan.badge === 'BEST VALUE' && styles.planCardHighlighted,
          ]}
          onPress={() => handleSelectPlan(plan)}
          disabled={!!processingPlan}
          data-testid={`plan-${plan.id}`}
        >
          {plan.badge && (
            <View style={[
              styles.badge,
              plan.badge === 'BEST VALUE' && styles.badgeBestValue,
              plan.badge === 'LIMITED TIME' && styles.badgeLimited,
            ]}>
              <Text style={styles.badgeText}>{plan.badge}</Text>
            </View>
          )}

          <View style={styles.planHeader}>
            <Text style={styles.planName}>{plan.name}</Text>
            <Text style={styles.planDescription}>{plan.description}</Text>
          </View>

          <View style={styles.priceContainer}>
            {plan.original_price && (
              <Text style={styles.originalPrice}>
                ${plan.original_price}
              </Text>
            )}
            <View style={styles.priceRow}>
              <Text style={styles.price}>${plan.price}</Text>
              <Text style={styles.interval}>/{plan.interval}</Text>
            </View>
            {plan.discount_percent && (
              <Text style={styles.discountLabel}>
                Save {plan.discount_percent}%
              </Text>
            )}
          </View>

          <View style={styles.trialBadge}>
            <Ionicons name="gift" size={16} color="#34C759" />
            <Text style={styles.trialText}>
              {plan.trial_days}-day free trial
            </Text>
          </View>

          <View style={styles.featuresContainer}>
            {plan.features.map((feature, index) => (
              <View key={index} style={styles.featureRow}>
                <Ionicons name="checkmark-circle" size={18} color="#34C759" />
                <Text style={styles.featureText}>{feature}</Text>
              </View>
            ))}
          </View>

          {plan.terms && (
            <Text style={styles.planTerms}>{plan.terms}</Text>
          )}

          <TouchableOpacity
            style={[
              styles.selectButton,
              plan.badge === 'BEST VALUE' && styles.selectButtonHighlighted,
              processingPlan === plan.id && styles.selectButtonDisabled,
            ]}
            onPress={() => handleSelectPlan(plan)}
            disabled={!!processingPlan}
          >
            {processingPlan === plan.id ? (
              <ActivityIndicator color={colors.text} />
            ) : (
              <Text style={styles.selectButtonText}>
                Start Free Trial
              </Text>
            )}
          </TouchableOpacity>
        </TouchableOpacity>
      ))}
    </>
  );

  const renderStorePlan = () => (
    <View style={styles.storePlanContainer}>
      {/* User Count Selector */}
      <View style={styles.userCountSection}>
        <Text style={styles.userCountLabel}>Number of Users</Text>
        <View style={styles.userCountRow}>
          <TouchableOpacity
            style={styles.userCountButton}
            onPress={() => setUserCount(Math.max(5, userCount - 1))}
          >
            <Ionicons name="remove" size={24} color={colors.text} />
          </TouchableOpacity>
          <View style={styles.userCountDisplay}>
            <Text style={styles.userCountNumber}>{userCount}</Text>
            <Text style={styles.userCountText}>users</Text>
          </View>
          <TouchableOpacity
            style={styles.userCountButton}
            onPress={() => setUserCount(userCount + 1)}
          >
            <Ionicons name="add" size={24} color={colors.text} />
          </TouchableOpacity>
        </View>
        {userCount < 5 && (
          <Text style={styles.minUsersWarning}>Minimum 5 users required</Text>
        )}
      </View>

      {/* Pricing Card */}
      <View style={[styles.planCard, userCount >= 6 && styles.planCardHighlighted]}>
        {userCount >= 6 && (
          <View style={[styles.badge, styles.badgeBestValue]}>
            <Text style={styles.badgeText}>VOLUME DISCOUNT</Text>
          </View>
        )}

        <View style={styles.planHeader}>
          <Text style={styles.planName}>Account Plan</Text>
          <Text style={styles.planDescription}>
            {userCount >= 6 ? 'Volume pricing for 6+ users' : 'For dealerships & sales teams'}
          </Text>
        </View>

        <View style={styles.priceContainer}>
          {userCount >= 6 && (
            <Text style={styles.originalPrice}>
              ${75}/user
            </Text>
          )}
          <View style={styles.priceRow}>
            <Text style={styles.price}>${storePricePerUser}</Text>
            <Text style={styles.interval}>/user/month</Text>
          </View>
          {userCount >= 6 && (
            <Text style={styles.discountLabel}>
              Save $10/user/month
            </Text>
          )}
        </View>

        <View style={styles.totalSection}>
          <Text style={styles.totalLabel}>Monthly Total ({userCount} users)</Text>
          <Text style={styles.totalAmount}>${storeTotal.toFixed(2)}</Text>
        </View>

        <View style={styles.trialBadge}>
          <Ionicons name="gift" size={16} color="#34C759" />
          <Text style={styles.trialText}>
            7-day free trial
          </Text>
        </View>

        <View style={styles.featuresContainer}>
          <View style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={styles.featureText}>Team management dashboard</Text>
          </View>
          <View style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={styles.featureText}>Account-level analytics</Text>
          </View>
          <View style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={styles.featureText}>Shared contact lists</Text>
          </View>
          <View style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={styles.featureText}>Campaign templates</Text>
          </View>
          <View style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={styles.featureText}>Cancel with 30 days notice</Text>
          </View>
          {userCount >= 6 && (
            <>
              <View style={styles.featureRow}>
                <Ionicons name="checkmark-circle" size={18} color="#34C759" />
                <Text style={styles.featureText}>Priority onboarding</Text>
              </View>
              <View style={styles.featureRow}>
                <Ionicons name="checkmark-circle" size={18} color="#34C759" />
                <Text style={styles.featureText}>Dedicated support</Text>
              </View>
            </>
          )}
        </View>

        <TouchableOpacity
          style={[
            styles.selectButton,
            userCount >= 6 && styles.selectButtonHighlighted,
            processingPlan && styles.selectButtonDisabled,
          ]}
          onPress={() => handleSelectPlan({ ...storePlans[0], type: 'store' })}
          disabled={!!processingPlan || userCount < 5}
        >
          {processingPlan ? (
            <ActivityIndicator color={colors.text} />
          ) : (
            <Text style={styles.selectButtonText}>
              Start Free Trial
            </Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Volume Pricing Info */}
      <View style={styles.volumeInfoCard}>
        <Ionicons name="information-circle" size={24} color="#007AFF" />
        <View style={styles.volumeInfoContent}>
          <Text style={styles.volumeInfoTitle}>Volume Pricing</Text>
          <Text style={styles.volumeInfoText}>
            • 5 users: $75/user/month = $375/month{'\n'}
            • 6+ users: $65/user/month (save $10/user)
          </Text>
        </View>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Choose Your Plan</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Tab Switcher */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'individual' && styles.tabActive]}
          onPress={() => setActiveTab('individual')}
        >
          <Ionicons 
            name="person" 
            size={18} 
            color={activeTab === 'individual' ? '#FFF' : colors.textSecondary} 
          />
          <Text style={[styles.tabText, activeTab === 'individual' && styles.tabTextActive]}>
            Individual
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'store' && styles.tabActive]}
          onPress={() => setActiveTab('store')}
        >
          <Ionicons 
            name="storefront" 
            size={18} 
            color={activeTab === 'store' ? '#FFF' : colors.textSecondary} 
          />
          <Text style={[styles.tabText, activeTab === 'store' && styles.tabTextActive]}>
            Account / Team
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Hero Section */}
        <View style={styles.heroSection}>
          <Text style={styles.heroTitle}>i'M On Social</Text>
          <Text style={styles.heroSubtitle}>
            {activeTab === 'individual' 
              ? 'The complete relationship management platform'
              : 'Empower your entire sales team'}
          </Text>
        </View>

        {/* Plans */}
        {activeTab === 'individual' ? renderIndividualPlans() : renderStorePlan()}

        {/* Terms */}
        <View style={styles.termsSection}>
          <Text style={styles.termsTitle}>Subscription Terms</Text>
          <View style={styles.termItem}>
            <Ionicons name="shield-checkmark" size={20} color={colors.textSecondary} />
            <Text style={styles.termText}>
              Cancel anytime with 30 days notice through the app
            </Text>
          </View>
          <View style={styles.termItem}>
            <Ionicons name="refresh" size={20} color={colors.textSecondary} />
            <Text style={styles.termText}>
              Subscriptions auto-renew unless cancelled
            </Text>
          </View>
          <View style={styles.termItem}>
            <Ionicons name="card" size={20} color={colors.textSecondary} />
            <Text style={styles.termText}>
              Secure payment processing by Stripe
            </Text>
          </View>
        </View>

        {/* Footer Links */}
        <View style={styles.footerLinks}>
          <TouchableOpacity onPress={() => router.push('/terms')}>
            <Text style={styles.footerLink}>Terms of Service</Text>
          </TouchableOpacity>
          <Text style={styles.footerDivider}>•</Text>
          <TouchableOpacity onPress={() => router.push('/privacy')}>
            <Text style={styles.footerLink}>Privacy Policy</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
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
    justifyContent: 'center',
    alignItems: 'center',
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
  },
  heroSection: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  heroTitle: {
    fontSize: 32,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  heroSubtitle: {
    fontSize: 18,
    color: colors.textSecondary,
    textAlign: 'center',
    maxWidth: 300,
  },
  planCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  planCardHighlighted: {
    borderColor: '#007AFF',
    borderWidth: 2,
  },
  badge: {
    position: 'absolute',
    top: -12,
    right: 16,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeBestValue: {
    backgroundColor: '#007AFF',
  },
  badgeLimited: {
    backgroundColor: '#FF9500',
  },
  badgeText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '700',
  },
  planHeader: {
    marginBottom: 16,
  },
  planName: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 4,
  },
  planDescription: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  priceContainer: {
    marginBottom: 16,
  },
  originalPrice: {
    fontSize: 18,
    color: colors.textSecondary,
    textDecorationLine: 'line-through',
    marginBottom: 4,
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  price: {
    fontSize: 42,
    fontWeight: '700',
    color: colors.text,
  },
  interval: {
    fontSize: 19,
    color: colors.textSecondary,
    marginLeft: 4,
  },
  discountLabel: {
    fontSize: 16,
    color: '#34C759',
    fontWeight: '600',
    marginTop: 4,
  },
  trialBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#34C75920',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginBottom: 16,
    gap: 6,
  },
  trialText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#34C759',
  },
  featuresContainer: {
    marginBottom: 16,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 10,
  },
  featureText: {
    fontSize: 16,
    color: colors.text,
    flex: 1,
  },
  planTerms: {
    fontSize: 14,
    color: colors.textSecondary,
    fontStyle: 'italic',
    marginBottom: 16,
  },
  selectButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  selectButtonHighlighted: {
    backgroundColor: '#007AFF',
  },
  selectButtonDisabled: {
    opacity: 0.6,
  },
  selectButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  termsSection: {
    paddingVertical: 24,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
    marginTop: 8,
  },
  termsTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  termItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 12,
  },
  termText: {
    fontSize: 16,
    color: colors.textSecondary,
    flex: 1,
  },
  footerLinks: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 24,
    gap: 12,
  },
  footerLink: {
    fontSize: 16,
    color: '#007AFF',
  },
  footerDivider: {
    color: colors.textSecondary,
  },
  // Tab styles
  tabContainer: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 16,
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
    fontSize: 17,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  tabTextActive: {
    color: colors.text,
  },
  // Store plan styles
  storePlanContainer: {
    marginTop: 8,
  },
  userCountSection: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    alignItems: 'center',
  },
  userCountLabel: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  userCountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 20,
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
    minWidth: 80,
  },
  userCountNumber: {
    fontSize: 48,
    fontWeight: '700',
    color: colors.text,
  },
  userCountText: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: -4,
  },
  minUsersWarning: {
    fontSize: 15,
    color: '#FF3B30',
    marginTop: 12,
  },
  totalSection: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    alignItems: 'center',
  },
  totalLabel: {
    fontSize: 16,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  totalAmount: {
    fontSize: 32,
    fontWeight: '700',
    color: '#34C759',
  },
  volumeInfoCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    gap: 12,
    alignItems: 'flex-start',
  },
  volumeInfoContent: {
    flex: 1,
  },
  volumeInfoTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 6,
  },
  volumeInfoText: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
