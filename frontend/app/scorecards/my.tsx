import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { RepScores } from '../../components/scorecards/RepScores';

export default function MyCallScores() {
  const { open } = useLocalSearchParams<{ open?: string }>();
  return <RepScores mine openId={open || null} />;
}
