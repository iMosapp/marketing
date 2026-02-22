import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

export default function MyAgreementScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [agreement, setAgreement] = useState<any>(null);
  
  useFocusEffect(
    useCallback(() => {
      loadAgreement();
    }, [user?._id])
  );
  
  const loadAgreement = async () => {
    if (!user?._id) return;
    
    try {
      setLoading(true);
      // Try to get user's agreement from partner agreements
      const res = await api.get(`/partners/user/${user._id}/agreement`);
      setAgreement(res.data);
    } catch (error: any) {
      console.error('Failed to load agreement:', error);
      // No agreement found is okay
      if (error.response?.status !== 404) {
        console.error('Error loading agreement');
      }
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await loadAgreement();
    setRefreshing(false);
  };
  
  const handleBack = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/admin');
    }
  };
  
  const openAgreementPDF = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    if (agreement?.pdf_url) {
      Linking.openURL(agreement.pdf_url);
    }
  };
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      </SafeAreaView>
    );
  }
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={handleBack} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>My Agreement</Text>
        <View style={{ width: 40 }} />
      </View>
      
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {!agreement ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="document-text-outline" size={64} color="#3C3C3E" />
            <Text style={styles.emptyTitle}>No Agreement Found</Text>
            <Text style={styles.emptySubtitle}>
              Your signed agreement will appear here once it's been processed
            </Text>
            <TouchableOpacity 
              style={styles.supportButton}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                Linking.openURL('mailto:support@imosapp.com?subject=Agreement%20Question');
              }}
            >
              <Ionicons name="help-circle-outline" size={18} color="#007AFF" />
              <Text style={styles.supportButtonText}>Request Support</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Agreement Status Card */}
            <View style={styles.statusCard}>
              <View style={styles.statusHeader}>
                <View style={[
                  styles.statusBadge,
                  { backgroundColor: agreement.status === 'active' ? '#34C759' : '#FF9500' }
                ]}>
                  <Ionicons 
                    name={agreement.status === 'active' ? 'checkmark-circle' : 'time'} 
                    size={16} 
                    color="#FFF" 
                  />
                  <Text style={styles.statusText}>
                    {agreement.status === 'active' ? 'Active' : 'Pending'}
                  </Text>
                </View>
              </View>
              
              <Text style={styles.agreementTitle}>{agreement.title || 'Partner Agreement'}</Text>
              
              {agreement.signed_at && (
                <View style={styles.infoRow}>
                  <Ionicons name="create-outline" size={18} color="#8E8E93" />
                  <Text style={styles.infoLabel}>Signed:</Text>
                  <Text style={styles.infoValue}>
                    {new Date(agreement.signed_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </Text>
                </View>
              )}
              
              {agreement.effective_date && (
                <View style={styles.infoRow}>
                  <Ionicons name="calendar-outline" size={18} color="#8E8E93" />
                  <Text style={styles.infoLabel}>Effective:</Text>
                  <Text style={styles.infoValue}>
                    {new Date(agreement.effective_date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </Text>
                </View>
              )}
              
              {agreement.expiration_date && (
                <View style={styles.infoRow}>
                  <Ionicons name="hourglass-outline" size={18} color="#8E8E93" />
                  <Text style={styles.infoLabel}>Expires:</Text>
                  <Text style={styles.infoValue}>
                    {new Date(agreement.expiration_date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </Text>
                </View>
              )}
            </View>
            
            {/* Agreement Details */}
            {(agreement.commission_rate || agreement.monthly_fee) && (
              <View style={styles.detailsCard}>
                <Text style={styles.detailsTitle}>Agreement Terms</Text>
                
                {agreement.commission_rate && (
                  <View style={styles.termRow}>
                    <Text style={styles.termLabel}>Commission Rate</Text>
                    <Text style={styles.termValue}>{agreement.commission_rate}%</Text>
                  </View>
                )}
                
                {agreement.monthly_fee && (
                  <View style={styles.termRow}>
                    <Text style={styles.termLabel}>Monthly Fee</Text>
                    <Text style={styles.termValue}>${agreement.monthly_fee}/mo</Text>
                  </View>
                )}
                
                {agreement.seats && (
                  <View style={styles.termRow}>
                    <Text style={styles.termLabel}>Included Seats</Text>
                    <Text style={styles.termValue}>{agreement.seats}</Text>
                  </View>
                )}
              </View>
            )}
            
            {/* Actions */}
            {agreement.pdf_url && (
              <TouchableOpacity style={styles.downloadButton} onPress={openAgreementPDF}>
                <Ionicons name="document-attach" size={20} color="#000" />
                <Text style={styles.downloadButtonText}>View Full Agreement (PDF)</Text>
              </TouchableOpacity>
            )}
            
            {/* Signer Info */}
            {agreement.signer_name && (
              <View style={styles.signerCard}>
                <Text style={styles.signerLabel}>Signed by</Text>
                <Text style={styles.signerName}>{agreement.signer_name}</Text>
                {agreement.signer_email && (
                  <Text style={styles.signerEmail}>{agreement.signer_email}</Text>
                )}
              </View>
            )}
          </>
        )}
      </ScrollView>
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
  content: {
    padding: 16,
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 80,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 32,
  },
  supportButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF20',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 20,
    marginTop: 24,
    gap: 8,
  },
  supportButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#007AFF',
  },
  statusCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
  },
  statusHeader: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginBottom: 12,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 6,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#FFF',
  },
  agreementTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 16,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 8,
  },
  infoLabel: {
    fontSize: 14,
    color: '#8E8E93',
  },
  infoValue: {
    fontSize: 14,
    color: '#FFF',
    fontWeight: '500',
  },
  detailsCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
  },
  detailsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 16,
  },
  termRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  termLabel: {
    fontSize: 15,
    color: '#8E8E93',
  },
  termValue: {
    fontSize: 17,
    fontWeight: '600',
    color: '#C9A962',
  },
  downloadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 10,
    marginBottom: 16,
  },
  downloadButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  signerCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  signerLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 4,
  },
  signerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  signerEmail: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 2,
  },
});
