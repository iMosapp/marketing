/**
 * OptimizedImage - Drop-in replacement for React Native's Image component.
 * Uses expo-image for disk caching, progressive loading, and blur placeholders.
 *
 * Usage: <OptimizedImage source={{ uri: "/api/images/..." }} style={...} />
 *        <OptimizedImage source={{ uri: "/api/images/..." }} variant="thumbnail" />
 */
import React from 'react';
import { Image as ExpoImage } from 'expo-image';
import { StyleProp, ImageStyle } from 'react-native';

// Blurhash placeholder — neutral gray, renders instantly
const PLACEHOLDER_BLUR = '|rF?hV%2WCj[ayj[a|j[az_NaeWBj@ayfRayfQfQM{M|azj[azf6fQfQfQIpWXofj[ayj[j[fQayWCoeoeaya}j[ayfQa{oLj?j[WVj[ayayj[fQoff7telecom';

type OptimizedImageProps = {
  source: { uri: string } | number;
  style?: StyleProp<ImageStyle>;
  contentFit?: 'cover' | 'contain' | 'fill' | 'none' | 'scale-down';
  placeholder?: string | null;
  transition?: number;
  cachePolicy?: 'none' | 'disk' | 'memory' | 'memory-disk';
  recyclingKey?: string;
  accessibilityLabel?: string;
  onError?: () => void;
  onLoad?: () => void;
};

export function OptimizedImage({
  source,
  style,
  contentFit = 'cover',
  placeholder = PLACEHOLDER_BLUR,
  transition = 200,
  cachePolicy = 'memory-disk',
  recyclingKey,
  accessibilityLabel,
  onError,
  onLoad,
}: OptimizedImageProps) {
  return (
    <ExpoImage
      source={source}
      style={style}
      contentFit={contentFit}
      placeholder={placeholder ? { blurhash: placeholder } : undefined}
      transition={transition}
      cachePolicy={cachePolicy}
      recyclingKey={recyclingKey}
      accessibilityLabel={accessibilityLabel}
      onError={onError}
      onLoad={onLoad}
    />
  );
}

export default OptimizedImage;
