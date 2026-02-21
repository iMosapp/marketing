import React, { useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Animated,
  Alert,
} from 'react-native';
import { Swipeable, RectButton } from 'react-native-gesture-handler';
import { Ionicons } from '@expo/vector-icons';

interface SwipeableConversationItemProps {
  children: React.ReactNode;
  conversationId: string;
  isRead: boolean;
  isArchived?: boolean;
  onArchive: (id: string) => void;
  onToggleRead: (id: string, isRead: boolean) => void;
  onCall: (id: string) => void;
  onDelete?: (id: string) => void;
}

export default function SwipeableConversationItem({
  children,
  conversationId,
  isRead,
  isArchived = false,
  onArchive,
  onToggleRead,
  onCall,
  onDelete,
}: SwipeableConversationItemProps) {
  const swipeableRef = useRef<Swipeable>(null);

  const closeSwipeable = () => {
    swipeableRef.current?.close();
  };

  const handleArchive = () => {
    closeSwipeable();
    onArchive(conversationId);
  };

  const handleToggleRead = () => {
    closeSwipeable();
    onToggleRead(conversationId, isRead);
  };

  const handleCall = () => {
    closeSwipeable();
    onCall(conversationId);
  };

  const handleDelete = () => {
    closeSwipeable();
    Alert.alert(
      'Delete Conversation',
      'Are you sure you want to delete this conversation? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => onDelete?.(conversationId),
        },
      ]
    );
  };

  // Left swipe actions (swipe right to reveal)
  const renderLeftActions = (
    progress: Animated.AnimatedInterpolation<number>,
    dragX: Animated.AnimatedInterpolation<number>
  ) => {
    const scale = dragX.interpolate({
      inputRange: [0, 80],
      outputRange: [0, 1],
      extrapolate: 'clamp',
    });

    return (
      <View style={styles.leftActionsContainer}>
        {/* Mark Read/Unread */}
        <RectButton style={[styles.actionButton, styles.readButton]} onPress={handleToggleRead}>
          <Animated.View style={[styles.actionContent, { transform: [{ scale }] }]}>
            <Ionicons
              name={isRead ? 'mail-unread' : 'mail-open'}
              size={22}
              color="#FFF"
            />
            <Text style={styles.actionText}>{isRead ? 'Unread' : 'Read'}</Text>
          </Animated.View>
        </RectButton>

        {/* Quick Call */}
        <RectButton style={[styles.actionButton, styles.callButton]} onPress={handleCall}>
          <Animated.View style={[styles.actionContent, { transform: [{ scale }] }]}>
            <Ionicons name="call" size={22} color="#FFF" />
            <Text style={styles.actionText}>Call</Text>
          </Animated.View>
        </RectButton>
      </View>
    );
  };

  // Right swipe actions (swipe left to reveal)
  const renderRightActions = (
    progress: Animated.AnimatedInterpolation<number>,
    dragX: Animated.AnimatedInterpolation<number>
  ) => {
    const scale = dragX.interpolate({
      inputRange: [-160, 0],
      outputRange: [1, 0],
      extrapolate: 'clamp',
    });

    return (
      <View style={styles.rightActionsContainer}>
        {/* Archive */}
        <RectButton style={[styles.actionButton, styles.archiveButton]} onPress={handleArchive}>
          <Animated.View style={[styles.actionContent, { transform: [{ scale }] }]}>
            <Ionicons
              name={isArchived ? 'arrow-undo' : 'archive'}
              size={22}
              color="#FFF"
            />
            <Text style={styles.actionText}>{isArchived ? 'Restore' : 'Archive'}</Text>
          </Animated.View>
        </RectButton>

        {/* Delete */}
        {onDelete && (
          <RectButton style={[styles.actionButton, styles.deleteButton]} onPress={handleDelete}>
            <Animated.View style={[styles.actionContent, { transform: [{ scale }] }]}>
              <Ionicons name="trash" size={22} color="#FFF" />
              <Text style={styles.actionText}>Delete</Text>
            </Animated.View>
          </RectButton>
        )}
      </View>
    );
  };

  return (
    <Swipeable
      ref={swipeableRef}
      friction={2}
      leftThreshold={40}
      rightThreshold={40}
      renderLeftActions={renderLeftActions}
      renderRightActions={renderRightActions}
      overshootLeft={false}
      overshootRight={false}
    >
      {children}
    </Swipeable>
  );
}

const styles = StyleSheet.create({
  leftActionsContainer: {
    flexDirection: 'row',
  },
  rightActionsContainer: {
    flexDirection: 'row',
  },
  actionButton: {
    width: 80,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionContent: {
    alignItems: 'center',
    gap: 4,
  },
  actionText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '500',
  },
  readButton: {
    backgroundColor: '#007AFF',
  },
  callButton: {
    backgroundColor: '#34C759',
  },
  archiveButton: {
    backgroundColor: '#8E8E93',
  },
  deleteButton: {
    backgroundColor: '#FF3B30',
  },
});
