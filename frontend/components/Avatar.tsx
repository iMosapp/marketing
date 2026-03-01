import React from 'react';
import { View, Text, Image, StyleSheet, ViewStyle, TextStyle, ImageStyle } from 'react-native';

interface AvatarProps {
  name?: string;
  photo?: string | null;
  size?: 'small' | 'medium' | 'large' | 'xlarge';
  style?: ViewStyle;
  textStyle?: TextStyle;
  showRing?: boolean;
  ringColor?: string;
  backgroundColor?: string;
}

const SIZES = {
  small: { container: 32, text: 12 },
  medium: { container: 44, text: 16 },
  large: { container: 56, text: 20 },
  xlarge: { container: 80, text: 28 },
};

// Generate consistent color based on name
const getColorFromName = (name: string): string => {
  const colors = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
    '#F8B500', '#00CED1', '#FF69B4', '#32CD32', '#FF7F50',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
};

const getInitials = (name: string): string => {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) {
    return parts[0].substring(0, 2).toUpperCase();
  }
  return (parts[0][0] + (parts[parts.length - 1][0] || '')).toUpperCase();
};

export const Avatar: React.FC<AvatarProps> = ({
  name = '',
  photo,
  size = 'medium',
  style,
  textStyle,
  showRing = false,
  ringColor = '#007AFF',
  backgroundColor,
}) => {
  const dimensions = SIZES[size];
  const bgColor = backgroundColor || getColorFromName(name);
  const initials = getInitials(name);

  const containerStyle: ViewStyle = {
    width: dimensions.container,
    height: dimensions.container,
    borderRadius: dimensions.container / 2,
    overflow: 'hidden',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: bgColor,
  };

  const imageStyle: ImageStyle = {
    width: dimensions.container,
    height: dimensions.container,
    borderRadius: dimensions.container / 2,
    resizeMode: 'cover',
  };

  const initialsStyle: TextStyle = {
    fontSize: dimensions.text,
    fontWeight: '600',
    color: '#FFFFFF',
  };

  const ringStyle: ViewStyle = showRing ? {
    borderWidth: 2,
    borderColor: ringColor,
  } : {};

  if (photo) {
    return (
      <View style={[containerStyle, ringStyle, style]}>
        <Image source={{ uri: photo }} style={imageStyle} />
      </View>
    );
  }

  return (
    <View style={[containerStyle, ringStyle, style]}>
      <Text style={[initialsStyle, textStyle]}>{initials}</Text>
    </View>
  );
};

// Convenience component for user avatars (admins, managers, reps)
export const UserAvatar: React.FC<AvatarProps & { role?: string }> = ({
  role,
  ...props
}) => {
  const roleColors: Record<string, string> = {
    super_admin: '#FF3B30',
    org_admin: '#FF9500',
    store_manager: '#5856D6',
    sales_rep: '#007AFF',
    user: '#34C759',
    independent: '#00CED1',
  };

  return (
    <Avatar
      {...props}
      backgroundColor={props.backgroundColor || (role ? roleColors[role] : undefined)}
    />
  );
};

// Convenience component for contact avatars
export const ContactAvatar: React.FC<AvatarProps> = (props) => {
  return <Avatar {...props} />;
};

export default Avatar;
