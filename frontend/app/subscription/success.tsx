import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

export default function SubscriptionSuccessPage() {
  const router = useRouter();
  const { session_id } = useLocalSearchParams();
  const [status, setStatus] = useState<'checking' | 'success' | 'pending' | 'error'>('checking');
  const [attempts, setAttempts] = useState(0);
  const maxAttempts = 5;

  useEffect(() => {
    if (session_id) {
      pollPaymentStatus();
    } else {
      setStatus('error');
    }
  }, [session_id]);

  const pollPaymentStatus = async () => {
    if (attempts >= maxAttempts) {
      setStatus('pending');
      return;
    }

    try {
      const response = await api.get(`/subscriptions/checkout/status/${session_id}`);
      
      if (response.data.payment_status === 'paid') {
        setStatus('success');
        return;
      } else if (response.data.status === 'expired') {
        setStatus('error');
        return;
      }
      
      // Still pending, try again
      setAttempts(prev => prev + 1);
      setTimeout(pollPaymentStatus, 2000);
    } catch (error) {
      console.error('Error checking payment:', error);
      setStatus('error');
    }
  };

  const renderContent = () => {
    switch (status) {
      case 'checking':
        return (
          <>
            <ActivityIndicator size="large" color="#007AFF" />
            <Text style={styles.title}>Verifying Payment</Text>
            <Text style={styles.subtitle}>
              Please wait while we confirm your subscription...
            </Text>
          </>
        );
      
      case 'success':
        return (
          <>
            <View style={styles.iconContainer}>
              <Ionicons name="checkmark-circle" size={80} color="#34C759" />
            </View>
            <Text style={styles.title}>Welcome to iMOs Pro!</Text>
            <Text style={styles.subtitle}>
              Your subscription is now active. You have 7 days to explore all features before billing begins.
            </Text>
            
            <View style={styles.benefitsContainer}>
              <Text style={styles.benefitsTitle}>What's Included:</Text>
              <View style={styles.benefitRow}>
                <Ionicons name="checkmark" size={20} color="#34C759" />
                <Text style={styles.benefitText}>Unlimited contacts</Text>
              </View>
              <View style={styles.benefitRow}>
                <Ionicons name="checkmark" size={20} color="#34C759" />
                <Text style={styles.benefitText}>AI-powered messaging</Text>
              </View>
              <View style={styles.benefitRow}>
                <Ionicons name="checkmark" size={20} color="#34C759" />
                <Text style={styles.benefitText}>Campaign automation</Text>
              </View>
              <View style={styles.benefitRow}>
                <Ionicons name="checkmark" size={20} color="#34C759" />
                <Text style={styles.benefitText}>Digital business cards</Text>
              </View>
            </View>
            
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => router.replace('/(tabs)/inbox')}
            >
              <Text style={styles.primaryButtonText}>Get Started</Text>
            </TouchableOpacity>
          </>
        );
      
      case 'pending':
        return (
          <>
            <View style={styles.iconContainer}>
              <Ionicons name="time" size={80} color="#FF9500" />
            </View>
            <Text style={styles.title}>Payment Processing</Text>
            <Text style={styles.subtitle}>
              Your payment is being processed. You'll receive a confirmation email shortly.
            </Text>
            
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => router.replace('/(tabs)/inbox')}
            >
              <Text style={styles.primaryButtonText}>Continue to App</Text>
            </TouchableOpacity>
          </>
        );
      
      case 'error':
        return (
          <>
            <View style={styles.iconContainer}>
              <Ionicons name="alert-circle" size={80} color="#FF3B30" />
            </View>
            <Text style={styles.title}>Something Went Wrong</Text>
            <Text style={styles.subtitle}>
              We couldn't verify your payment. Please contact support if you were charged.
            </Text>
            
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => router.replace('/subscription/pricing')}
            >
              <Text style={styles.primaryButtonText}>Try Again</Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={() => router.replace('/(tabs)/more')}
            >
              <Text style={styles.secondaryButtonText}>Contact Support</Text>
            </TouchableOpacity>
          </>
        );
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        {renderContent()}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  iconContainer: {
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
    marginBottom: 12,
  },
  subtitle: {
    fontSize: 16,
    color: '#8E8E93',
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 24,
  },
  benefitsContainer: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    marginBottom: 32,
  },
  benefitsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 16,
  },
  benefitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  benefitText: {
    fontSize: 15,
    color: '#FFF',
  },
  primaryButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 32,
    width: '100%',
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  secondaryButton: {
    paddingVertical: 16,
    paddingHorizontal: 32,
    width: '100%',
    alignItems: 'center',
  },
  secondaryButtonText: {
    fontSize: 17,
    fontWeight: '500',
    color: '#007AFF',
  },
});
