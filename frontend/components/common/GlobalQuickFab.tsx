import React from 'react';
import { useRouter } from 'expo-router';
import { QuickActionsFab, FabAction } from '../home/QuickActionsFab';

/** The gold + button from Home, for every main tab. Card opens the standalone share screen. */
export const GlobalQuickFab = () => {
  const router = useRouter();
  const actions: FabAction[] = [
    { key: 'dates-calendar', icon: 'calendar', label: 'Calendar', color: '#AF52DE', onPress: () => router.push('/dates-calendar' as any) },
    { key: 'review', icon: 'star', label: 'Review', color: '#FF9500', onPress: () => router.push('/quick-send/review' as any) },
    { key: 'card', icon: 'card', label: 'Card', color: '#007AFF', onPress: () => router.push('/quick-send/digitalcard' as any) },
    { key: 'new-contact', icon: 'person-add', label: 'Contact', color: '#AF52DE', onPress: () => router.push('/contact/new' as any) },
    { key: 'sold', icon: 'trophy', label: 'SOLD!', color: '#C9A962', onPress: () => router.push('/sold-quick' as any) },
  ];
  return <QuickActionsFab actions={actions} />;
};
