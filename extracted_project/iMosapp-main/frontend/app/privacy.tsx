import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../services/api';

export default function PrivacyPolicyPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [privacy, setPrivacy] = useState<{ title: string; last_updated: string; content: string } | null>(null);

  useEffect(() => {
    loadPrivacy();
  }, []);

  const loadPrivacy = async () => {
    try {
      const response = await api.get('/legal/privacy');
      setPrivacy(response.data);
    } catch (error) {
      console.error('Error loading privacy policy:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderMarkdown = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, index) => {
      if (line.startsWith('# ')) {
        return <Text key={index} style={styles.h1}>{line.substring(2)}</Text>;
      }
      if (line.startsWith('## ')) {
        return <Text key={index} style={styles.h2}>{line.substring(3)}</Text>;
      }
      if (line.startsWith('### ')) {
        return <Text key={index} style={styles.h3}>{line.substring(4)}</Text>;
      }
      if (line.startsWith('**') && line.endsWith('**')) {
        return <Text key={index} style={styles.bold}>{line.slice(2, -2)}</Text>;
      }
      if (line.startsWith('- ')) {
        return (
          <View key={index} style={styles.listItem}>
            <Text style={styles.bullet}>•</Text>
            <Text style={styles.listText}>{line.substring(2)}</Text>
          </View>
        );
      }
      if (line.startsWith('---')) {
        return <View key={index} style={styles.divider} />;
      }
      if (line.trim() === '') {
        return <View key={index} style={{ height: 12 }} />;
      }
      const parts = line.split(/(\*\*.*?\*\*)/g);
      if (parts.length > 1) {
        return (
          <Text key={index} style={styles.paragraph}>
            {parts.map((part, i) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <Text key={i} style={styles.boldInline}>{part.slice(2, -2)}</Text>;
              }
              return part;
            })}
          </Text>
        );
      }
      return <Text key={index} style={styles.paragraph}>{line}</Text>;
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
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Privacy Policy</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {privacy && (
            <View style={styles.contentInner}>
              <Text style={styles.lastUpdated}>Last Updated: {privacy.last_updated}</Text>
              {renderMarkdown(privacy.content)}
            </View>
          )}
          
          <View style={styles.footer}>
            <TouchableOpacity 
              style={styles.footerLink}
              onPress={() => router.push('/terms')}
            >
              <Ionicons name="document-text" size={20} color="#007AFF" />
              <Text style={styles.footerLinkText}>Terms of Service</Text>
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
    flex: 1,
  },
  contentInner: {
    padding: 20,
  },
  lastUpdated: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 20,
  },
  h1: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 16,
    marginTop: 8,
  },
  h2: {
    fontSize: 22,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 24,
    marginBottom: 12,
  },
  h3: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
    marginBottom: 8,
  },
  bold: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    marginVertical: 8,
  },
  boldInline: {
    fontWeight: '600',
  },
  paragraph: {
    fontSize: 15,
    color: '#CCC',
    lineHeight: 24,
    marginBottom: 4,
  },
  listItem: {
    flexDirection: 'row',
    paddingLeft: 8,
    marginBottom: 8,
  },
  bullet: {
    fontSize: 15,
    color: '#8E8E93',
    marginRight: 10,
    lineHeight: 24,
  },
  listText: {
    flex: 1,
    fontSize: 15,
    color: '#CCC',
    lineHeight: 24,
  },
  divider: {
    height: 1,
    backgroundColor: '#3C3C3E',
    marginVertical: 24,
  },
  footer: {
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: '#1C1C1E',
  },
  footerLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  footerLinkText: {
    fontSize: 16,
    color: '#007AFF',
  },
});
