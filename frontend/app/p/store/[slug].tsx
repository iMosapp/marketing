import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { PublicPageRedirect } from '../../../components/PublicPageRedirect';

export default function StoreLandingRoute() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  return <PublicPageRedirect kind="p/store" id={slug} />;
}
