import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { PublicPageRedirect } from '../../../components/PublicPageRedirect';

export default function StoreCardRoute() {
  const { storeSlug } = useLocalSearchParams<{ storeSlug: string }>();
  return <PublicPageRedirect kind="card/store" id={storeSlug} />;
}
