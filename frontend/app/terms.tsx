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
import { useThemeStore } from '../store/themeStore';

export default function TermsOfServicePage() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const [loading, setLoading] = useState(true);
  const [terms, setTerms] = useState<{ title: string; last_updated: string; content: string } | null>(null);

  useEffect(() => {
    loadTerms();
  }, []);

  const loadTerms = async () => {
    try {
      const response = await api.get('/legal/terms');
      setTerms(response.data);
    } catch (error) {
      console.error('Error loading terms:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderMarkdown = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, index) => {
      if (line.startsWith('# ')) {
        return <Text key={index} style={s.h1}>{line.substring(2)}</Text>;
      }
      if (line.startsWith('## ')) {
        return <Text key={index} style={s.h2}>{line.substring(3)}</Text>;
      }
      if (line.startsWith('### ')) {
        return <Text key={index} style={s.h3}>{line.substring(4)}</Text>;
      }
      if (line.startsWith('**') && line.endsWith('**')) {
        return <Text key={index} style={s.bold}>{line.slice(2, -2)}</Text>;
      }
      if (line.startsWith('- ')) {
        return (
          <View key={index} style={s.listItem}>
            <Text style={s.bullet}>•</Text>
            <Text style={s.listText}>{line.substring(2)}</Text>
          </View>
        );
      }
      if (line.startsWith('---')) {
        return <View key={index} style={s.divider} />;
      }
      if (line.trim() === '') {
        return <View key={index} style={{ height: 12 }} />;
      }
      const parts = line.split(/(\*\*.*?\*\*)/g);
      if (parts.length > 1) {
        return (
          <Text key={index} style={s.paragraph}>
            {parts.map((part, i) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <Text key={i} style={s.boldInline}>{part.slice(2, -2)}</Text>;
              }
              return part;
            })}
          </Text>
        );
      }
      return <Text key={index} style={s.paragraph}>{line}</Text>;
    });
  };

  if (loading) {
    return (
      <View style={s.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  return (
    <View style={s.container}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.backButton}>
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Terms of Service</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView style={s.content} showsVerticalScrollIndicator={false}>
          {terms && (
            <View style={s.contentInner}>
              <Text style={s.lastUpdated}>Last Updated: {terms.last_updated}</Text>
              {renderMarkdown(terms.content)}
            </View>
          )}
          
          <View style={s.footer}>
            <TouchableOpacity 
              style={s.footerLink}
              onPress={() => router.push('/privacy')}
            >
              <Ionicons name="shield-checkmark" size={20} color="#007AFF" />
              <Text style={s.footerLinkText}>Privacy Policy</Text>
            </TouchableOpacity>
          </View>
          
          <View style={{ height: 40 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.bg,
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
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    flex: 1,
  },
  contentInner: {
    padding: 20,
  },
  lastUpdated: {
    fontSize: 13,
    color: colors.textSecondary,
    marginBottom: 20,
  },
  h1: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 16,
    marginTop: 8,
  },
  h2: {
    fontSize: 22,
    fontWeight: '600',
    color: colors.text,
    marginTop: 24,
    marginBottom: 12,
  },
  h3: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
    marginBottom: 8,
  },
  bold: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginVertical: 8,
  },
  boldInline: {
    fontWeight: '600',
  },
  paragraph: {
    fontSize: 15,
    color: colors.textSecondary,
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
    color: colors.textSecondary,
    marginRight: 10,
    lineHeight: 24,
  },
  listText: {
    flex: 1,
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 24,
  },
  divider: {
    height: 1,
    backgroundColor: colors.surface,
    marginVertical: 24,
  },
  footer: {
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
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
