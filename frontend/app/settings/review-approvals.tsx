import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Image,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

interface PendingReview {
  id: string;
  customer_name: string;
  customer_phone?: string;
  customer_email?: string;
  rating: number;
  text: string;
  photo_url?: string;
  created_at: string;
}

export default function ReviewApprovalsScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [reviews, setReviews] = useState<PendingReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processing, setProcessing] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      fetchPendingReviews();
    }, [user?._id])
  );

  const fetchPendingReviews = async () => {
    if (!user?._id) return;
    
    try {
      const response = await api.get(`/p/reviews/pending/${user._id}`);
      setReviews(response.data);
    } catch (error) {
      console.error('Error fetching pending reviews:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleApprove = async (reviewId: string) => {
    setProcessing(reviewId);
    try {
      await api.post(`/p/reviews/approve/${reviewId}`);
      Alert.alert('Success', 'Review approved and will now be visible on your landing page.');
      setReviews(prev => prev.filter(r => r.id !== reviewId));
    } catch (error) {
      Alert.alert('Error', 'Failed to approve review');
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (reviewId: string) => {
    Alert.alert(
      'Reject Review',
      'Are you sure you want to reject this review? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reject',
          style: 'destructive',
          onPress: async () => {
            setProcessing(reviewId);
            try {
              await api.post(`/p/reviews/reject/${reviewId}`);
              Alert.alert('Removed', 'Review has been rejected.');
              setReviews(prev => prev.filter(r => r.id !== reviewId));
            } catch (error) {
              Alert.alert('Error', 'Failed to reject review');
            } finally {
              setProcessing(null);
            }
          },
        },
      ]
    );
  };

  const renderStars = (rating: number) => {
    return (
      <View style={styles.starsContainer}>
        {[1, 2, 3, 4, 5].map((star) => (
          <Ionicons
            key={star}
            name={star <= rating ? 'star' : 'star-outline'}
            size={16}
            color="#FFD700"
          />
        ))}
      </View>
    );
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

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
        <Text style={styles.headerTitle}>Review Approvals</Text>
        <View style={styles.placeholder} />
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              fetchPendingReviews();
            }}
            tintColor="#007AFF"
          />
        }
      >
        {reviews.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="checkmark-circle" size={64} color="#34C759" />
            <Text style={styles.emptyTitle}>All Caught Up!</Text>
            <Text style={styles.emptySubtitle}>
              No pending reviews to approve. New reviews will appear here.
            </Text>
          </View>
        ) : (
          <>
            <Text style={styles.sectionTitle}>
              {reviews.length} Pending Review{reviews.length !== 1 ? 's' : ''}
            </Text>
            {reviews.map((review) => (
              <View key={review.id} style={styles.reviewCard}>
                <View style={styles.reviewHeader}>
                  <View>
                    <Text style={styles.customerName}>{review.customer_name}</Text>
                    {review.created_at && (
                      <Text style={styles.dateText}>{formatDate(review.created_at)}</Text>
                    )}
                  </View>
                  {renderStars(review.rating)}
                </View>

                {review.text && (
                  <Text style={styles.reviewText}>"{review.text}"</Text>
                )}

                {review.photo_url && (
                  <Image
                    source={{ uri: review.photo_url }}
                    style={styles.reviewPhoto}
                    resizeMode="cover"
                  />
                )}

                {(review.customer_phone || review.customer_email) && (
                  <View style={styles.contactInfo}>
                    {review.customer_phone && (
                      <View style={styles.contactRow}>
                        <Ionicons name="call-outline" size={14} color="#8E8E93" />
                        <Text style={styles.contactText}>{review.customer_phone}</Text>
                      </View>
                    )}
                    {review.customer_email && (
                      <View style={styles.contactRow}>
                        <Ionicons name="mail-outline" size={14} color="#8E8E93" />
                        <Text style={styles.contactText}>{review.customer_email}</Text>
                      </View>
                    )}
                  </View>
                )}

                <View style={styles.actionButtons}>
                  <TouchableOpacity
                    style={styles.rejectButton}
                    onPress={() => handleReject(review.id)}
                    disabled={processing === review.id}
                  >
                    {processing === review.id ? (
                      <ActivityIndicator size="small" color="#FF3B30" />
                    ) : (
                      <>
                        <Ionicons name="close" size={20} color="#FF3B30" />
                        <Text style={styles.rejectButtonText}>Reject</Text>
                      </>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.approveButton}
                    onPress={() => handleApprove(review.id)}
                    disabled={processing === review.id}
                  >
                    {processing === review.id ? (
                      <ActivityIndicator size="small" color="#FFF" />
                    ) : (
                      <>
                        <Ionicons name="checkmark" size={20} color="#FFF" />
                        <Text style={styles.approveButtonText}>Approve</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </>
        )}

        <View style={{ height: 40 }} />
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
  placeholder: {
    width: 32,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 16,
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 40,
  },
  reviewCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  reviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  customerName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  dateText: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  starsContainer: {
    flexDirection: 'row',
    gap: 2,
  },
  reviewText: {
    fontSize: 15,
    color: '#CCC',
    fontStyle: 'italic',
    lineHeight: 22,
    marginBottom: 12,
  },
  reviewPhoto: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    marginBottom: 12,
  },
  contactInfo: {
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  contactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  contactText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  rejectButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF3B3020',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 6,
  },
  rejectButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FF3B30',
  },
  approveButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#34C759',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 6,
  },
  approveButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
});
