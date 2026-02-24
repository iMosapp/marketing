import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { showSimpleAlert } from '../services/alert';

const STORAGE_KEY = 'hidden_menu_items';

// All available menu items that can be hidden/shown
const ALL_MENU_ITEMS = [
  { id: 'ask-jessi', icon: 'sparkles', title: 'Ask Jessi', color: '#C9A962', category: 'AI & Help' },
  { id: 'digital-card', icon: 'card', title: 'My Digital Card', color: '#007AFF', category: 'Profile' },
  { id: 'ai-persona', icon: 'person', title: 'AI Persona Settings', color: '#AF52DE', category: 'Profile' },
  { id: 'tasks', icon: 'checkmark-done', title: 'Tasks & Reminders', color: '#34C759', category: 'Productivity' },
  { id: 'notifications', icon: 'notifications', title: 'Notifications', color: '#FF9500', category: 'Settings' },
  { id: 'broadcast', icon: 'megaphone', title: 'Broadcast', color: '#FF9500', category: 'Messaging' },
  { id: 'lead-sources', icon: 'git-branch', title: 'Lead Sources', color: '#5856D6', category: 'Sales' },
  { id: 'sms-campaigns', icon: 'chatbubbles', title: 'SMS Campaigns', color: '#FF2D55', category: 'Messaging' },
  { id: 'email-campaigns', icon: 'mail', title: 'Email Campaigns', color: '#AF52DE', category: 'Messaging' },
  { id: 'campaign-dashboard', icon: 'speedometer', title: 'Campaign Dashboard', color: '#5AC8FA', category: 'Messaging' },
  { id: 'analytics', icon: 'stats-chart', title: 'Analytics', color: '#34C759', category: 'Reports' },
  { id: 'reports', icon: 'bar-chart', title: 'Reports', color: '#007AFF', category: 'Reports' },
  { id: 'security', icon: 'shield-checkmark', title: 'Security', color: '#FF3B30', category: 'Settings' },
  { id: 'sms-email-toggle', icon: 'swap-horizontal-outline', title: 'SMS / Email Toggle', color: '#8E8E93', category: 'Settings' },
  { id: 'templates', icon: 'document-text', title: 'Message Templates', color: '#5856D6', category: 'Messaging' },
  { id: 'tags', icon: 'pricetag', title: 'Tags', color: '#FF9500', category: 'Organization' },
  { id: 'calendar', icon: 'calendar', title: 'Calendar', color: '#007AFF', category: 'Productivity' },
  { id: 'review-links', icon: 'star', title: 'Review Links', color: '#FFD60A', category: 'Sales' },
  { id: 'brand-kit', icon: 'color-palette', title: 'Brand Kit', color: '#FF2D55', category: 'Settings' },
  { id: 'integrations', icon: 'git-network', title: 'Integrations', color: '#8E8E93', category: 'Settings' },
  { id: 'congrats-template', icon: 'gift', title: 'Congrats Card', color: '#C9A962', category: 'Sales' },
];

// Group items by category
const groupByCategory = (items: typeof ALL_MENU_ITEMS) => {
  const groups: Record<string, typeof ALL_MENU_ITEMS> = {};
  items.forEach(item => {
    if (!groups[item.category]) {
      groups[item.category] = [];
    }
    groups[item.category].push(item);
  });
  return groups;
};

export default function CustomizeMenuScreen() {
  const router = useRouter();
  const [hiddenItems, setHiddenItems] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHiddenItems();
  }, []);

  const loadHiddenItems = async () => {
    try {
      const saved = await AsyncStorage.getItem(STORAGE_KEY);
      if (saved) {
        setHiddenItems(new Set(JSON.parse(saved)));
      }
    } catch (error) {
      console.error('Error loading hidden items:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleItem = async (itemId: string) => {
    const newHidden = new Set(hiddenItems);
    if (newHidden.has(itemId)) {
      newHidden.delete(itemId);
    } else {
      newHidden.add(itemId);
    }
    setHiddenItems(newHidden);
    
    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify([...newHidden]));
    } catch (error) {
      console.error('Error saving hidden items:', error);
    }
  };

  const showAll = async () => {
    setHiddenItems(new Set());
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify([]));
    showSimpleAlert('Reset', 'All menu items are now visible');
  };

  const hideAll = async () => {
    const allIds = ALL_MENU_ITEMS.map(item => item.id);
    setHiddenItems(new Set(allIds));
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(allIds));
    showSimpleAlert('Hidden', 'All optional items are now hidden');
  };

  const grouped = groupByCategory(ALL_MENU_ITEMS);
  const categories = Object.keys(grouped).sort();

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Customize Menu</Text>
        <View style={{ width: 28 }} />
      </View>

      {/* Info Banner */}
      <View style={styles.infoBanner}>
        <Ionicons name="information-circle" size={24} color="#007AFF" />
        <Text style={styles.infoText}>
          Toggle off features you don't use to keep your menu clean and simple.
        </Text>
      </View>

      {/* Quick Actions */}
      <View style={styles.quickActions}>
        <TouchableOpacity style={styles.quickButton} onPress={showAll}>
          <Ionicons name="eye" size={18} color="#34C759" />
          <Text style={styles.quickButtonText}>Show All</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.quickButton} onPress={hideAll}>
          <Ionicons name="eye-off" size={18} color="#FF9500" />
          <Text style={styles.quickButtonText}>Hide All</Text>
        </TouchableOpacity>
      </View>

      {/* Stats */}
      <View style={styles.statsContainer}>
        <Text style={styles.statsText}>
          Showing {ALL_MENU_ITEMS.length - hiddenItems.size} of {ALL_MENU_ITEMS.length} items
        </Text>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.scrollContent}>
        {categories.map(category => (
          <View key={category} style={styles.categorySection}>
            <Text style={styles.categoryTitle}>{category}</Text>
            <View style={styles.categoryItems}>
              {grouped[category].map(item => (
                <View key={item.id} style={styles.itemRow}>
                  <View style={styles.itemLeft}>
                    <View style={[styles.itemIcon, { backgroundColor: `${item.color}20` }]}>
                      <Ionicons name={item.icon as any} size={20} color={item.color} />
                    </View>
                    <Text style={[
                      styles.itemTitle,
                      hiddenItems.has(item.id) && styles.itemTitleHidden
                    ]}>
                      {item.title}
                    </Text>
                  </View>
                  <Switch
                    value={!hiddenItems.has(item.id)}
                    onValueChange={() => toggleItem(item.id)}
                    trackColor={{ false: '#3A3A3C', true: '#34C75980' }}
                    thumbColor={!hiddenItems.has(item.id) ? '#34C759' : '#8E8E93'}
                    ios_backgroundColor="#3A3A3C"
                  />
                </View>
              ))}
            </View>
          </View>
        ))}
        
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  infoBanner: {
    flexDirection: 'row',
    backgroundColor: '#007AFF15',
    margin: 16,
    padding: 16,
    borderRadius: 12,
    gap: 12,
    alignItems: 'center',
  },
  infoText: {
    flex: 1,
    fontSize: 14,
    color: '#FFF',
    lineHeight: 20,
  },
  quickActions: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 12,
    marginBottom: 8,
  },
  quickButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#1C1C1E',
    padding: 12,
    borderRadius: 10,
  },
  quickButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
  statsContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  statsText: {
    fontSize: 13,
    color: '#8E8E93',
    textAlign: 'center',
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
  },
  categorySection: {
    marginBottom: 24,
  },
  categoryTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  categoryItems: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    overflow: 'hidden',
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  itemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  itemIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: '500',
    color: '#FFF',
  },
  itemTitleHidden: {
    color: '#6E6E73',
    textDecorationLine: 'line-through',
  },
});
