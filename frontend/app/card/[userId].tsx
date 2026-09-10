import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { PublicPageRedirect } from '../../components/PublicPageRedirect';

export default function DigitalCardRoute() {
  const { userId } = useLocalSearchParams<{ userId: string }>();
  return <PublicPageRedirect kind="card" id={userId} />;
}
