import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { PublicPageRedirect } from '../../components/PublicPageRedirect';

export default function LandingPageRoute() {
  const { userId } = useLocalSearchParams<{ userId: string }>();
  return <PublicPageRedirect kind="p" id={userId} />;
}
