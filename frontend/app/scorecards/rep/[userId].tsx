import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { RepScores } from '../../../components/scorecards/RepScores';

export default function RepCallScores() {
  const { userId, open } = useLocalSearchParams<{ userId: string; open?: string }>();
  return <RepScores mine={false} userId={userId} openId={open || null} />;
}
