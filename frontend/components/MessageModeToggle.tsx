import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';

import { useThemeStore } from '../store/themeStore';
export type MessageMode = 'sms' | 'email';
export type ToggleStyle = 'pill' | 'fab' | 'tabs' | 'segmented';

interface MessageModeToggleProps {
  mode: MessageMode;
  onModeChange: (mode: MessageMode) => void;
  style?: ToggleStyle;
  size?: 'small' | 'medium' | 'large';
}

const triggerHaptic = () => {
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
};

// ============= PILL TOGGLE =============
const PillToggle: React.FC<MessageModeToggleProps> = ({ mode, onModeChange }) => {
  const handleToggle = () => {
    triggerHaptic();
    onModeChange(mode === 'sms' ? 'email' : 'sms');
  };

  return (
    <TouchableOpacity 
      style={[styles.pillContainer, mode === 'email' && styles.pillContainerEmail]}
      onPress={handleToggle}
      activeOpacity={0.8}
    >
      <View style={[styles.pillOption, mode === 'sms' && styles.pillOptionActive]}>
        <Ionicons 
          name="paper-plane" 
          size={16} 
          color={mode === 'sms' ? '#FFF' : '#8E8E93'} 
        />
        <Text style={[styles.pillText, mode === 'sms' && styles.pillTextActive]}>SMS</Text>
      </View>
      <View style={[styles.pillOption, mode === 'email' && styles.pillOptionActiveEmail]}>
        <Ionicons 
          name="mail" 
          size={16} 
          color={mode === 'email' ? '#000' : '#8E8E93'} 
        />
        <Text style={[styles.pillText, mode === 'email' && styles.pillTextActiveEmail]}>Email</Text>
      </View>
    </TouchableOpacity>
  );
};

// ============= FAB (FLOATING ACTION BUTTON) TOGGLE =============
const FabToggle: React.FC<MessageModeToggleProps> = ({ mode, onModeChange }) => {
  const handleToggle = () => {
    triggerHaptic();
    onModeChange(mode === 'sms' ? 'email' : 'sms');
  };

  return (
    <TouchableOpacity 
      style={[styles.fabButton, mode === 'email' && styles.fabButtonEmail]}
      onPress={handleToggle}
      activeOpacity={0.8}
    >
      <Ionicons 
        name={mode === 'sms' ? 'paper-plane' : 'mail'} 
        size={24} 
        color={mode === 'email' ? '#000' : '#FFF'} 
      />
    </TouchableOpacity>
  );
};

// ============= TABS TOGGLE =============
const TabsToggle: React.FC<MessageModeToggleProps> = ({ mode, onModeChange }) => {
  return (
    <View style={[styles.tabsContainer, mode === 'email' && styles.tabsContainerEmail]}>
      <TouchableOpacity 
        style={[styles.tabOption, mode === 'sms' && styles.tabOptionActive]}
        onPress={() => {
          triggerHaptic();
          onModeChange('sms');
        }}
        activeOpacity={0.8}
      >
        <Ionicons 
          name="paper-plane" 
          size={20} 
          color={mode === 'sms' ? '#007AFF' : '#8E8E93'} 
        />
        <Text style={[styles.tabText, mode === 'sms' && styles.tabTextActive]}>SMS</Text>
        {mode === 'sms' && <View style={styles.tabIndicator} />}
      </TouchableOpacity>
      <TouchableOpacity 
        style={[styles.tabOption, mode === 'email' && styles.tabOptionActiveEmail]}
        onPress={() => {
          triggerHaptic();
          onModeChange('email');
        }}
        activeOpacity={0.8}
      >
        <Ionicons 
          name="mail" 
          size={20} 
          color={mode === 'email' ? '#007AFF' : '#8E8E93'} 
        />
        <Text style={[styles.tabText, mode === 'email' && styles.tabTextActiveEmail]}>Email</Text>
        {mode === 'email' && <View style={[styles.tabIndicator, styles.tabIndicatorEmail]} />}
      </TouchableOpacity>
    </View>
  );
};

// ============= SEGMENTED CONTROL TOGGLE =============
const SegmentedToggle: React.FC<MessageModeToggleProps> = ({ mode, onModeChange }) => {
  return (
    <View style={[styles.segmentedContainer, mode === 'email' && styles.segmentedContainerEmail]}>
      <TouchableOpacity 
        style={[
          styles.segmentedOption, 
          mode === 'sms' && styles.segmentedOptionActive
        ]}
        onPress={() => {
          triggerHaptic();
          onModeChange('sms');
        }}
        activeOpacity={0.8}
      >
        <Ionicons 
          name="paper-plane" 
          size={18} 
          color={mode === 'sms' ? '#FFF' : '#8E8E93'} 
        />
        <Text style={[styles.segmentedText, mode === 'sms' && styles.segmentedTextActive]}>
          SMS
        </Text>
      </TouchableOpacity>
      <TouchableOpacity 
        style={[
          styles.segmentedOption, 
          mode === 'email' && styles.segmentedOptionActiveEmail
        ]}
        onPress={() => {
          triggerHaptic();
          onModeChange('email');
        }}
        activeOpacity={0.8}
      >
        <Ionicons 
          name="mail" 
          size={18} 
          color={mode === 'email' ? '#000' : '#8E8E93'} 
        />
        <Text style={[styles.segmentedText, mode === 'email' && styles.segmentedTextActiveEmail]}>
          Email
        </Text>
      </TouchableOpacity>
    </View>
  );
};

// ============= MAIN COMPONENT =============
const MessageModeToggle: React.FC<MessageModeToggleProps> = (props) => {
  const { style = 'pill' } = props;

  switch (style) {
    case 'fab':
      return <FabToggle {...props} />;
    case 'tabs':
      return <TabsToggle {...props} />;
    case 'segmented':
      return <SegmentedToggle {...props} />;
    case 'pill':
    default:
      return <PillToggle {...props} />;
  }
};

export default MessageModeToggle;

const styles = StyleSheet.create({
  // ============= PILL STYLES =============
  pillContainer: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
    padding: 4,
  },
  pillContainerEmail: {
    backgroundColor: '#3A3A3C',
  },
  pillOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 16,
    gap: 6,
  },
  pillOptionActive: {
    backgroundColor: '#007AFF',
  },
  pillOptionActiveEmail: {
    backgroundColor: '#1C1C1E',
  },
  pillText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#8E8E93',
  },
  pillTextActive: {
    color: '#FFFFFF',
  },
  pillTextActiveEmail: {
    color: '#FFFFFF',
  },

  // ============= FAB STYLES =============
  fabButton: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  fabButtonEmail: {
    backgroundColor: '#1C1C1E',
    borderWidth: 2,
    borderColor: '#007AFF',
  },

  // ============= TABS STYLES =============
  tabsContainer: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    overflow: 'hidden',
  },
  tabsContainerEmail: {
    backgroundColor: '#000000',
  },
  tabOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    gap: 8,
    position: 'relative',
  },
  tabOptionActive: {},
  tabOptionActiveEmail: {},
  tabText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#8E8E93',
  },
  tabTextActive: {
    color: '#007AFF',
  },
  tabTextActiveEmail: {
    color: '#007AFF',
  },
  tabIndicator: {
    position: 'absolute',
    bottom: 0,
    left: '25%',
    right: '25%',
    height: 3,
    backgroundColor: '#007AFF',
    borderRadius: 1.5,
  },
  tabIndicatorEmail: {
    backgroundColor: '#007AFF',
  },

  // ============= SEGMENTED STYLES =============
  segmentedContainer: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 4,
  },
  segmentedContainerEmail: {
    backgroundColor: '#3A3A3C',
  },
  segmentedOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    gap: 6,
  },
  segmentedOptionActive: {
    backgroundColor: '#007AFF',
  },
  segmentedOptionActiveEmail: {
    backgroundColor: '#1C1C1E',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  segmentedText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#8E8E93',
  },
  segmentedTextActive: {
    color: '#FFFFFF',
  },
  segmentedTextActiveEmail: {
    color: '#FFFFFF',
  },
});
