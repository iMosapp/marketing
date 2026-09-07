import React from 'react';
import { HealthScoreScreen } from '../components/health/HealthScoreScreen';

export default function GEOHealthScreen() {
  return (
    <HealthScoreScreen
      config={{
        kind: 'geo',
        title: 'GEO Health',
        guideRoute: '/geo-guide',
        factorIcons: { ai_identity: 'brain', conversational: 'chatbubbles', distribution: 'share-social', citation: 'link', freshness: 'flash' },
        factorColors: { ai_identity: '#AF52DE', conversational: '#C9A962', distribution: '#FF9500', citation: '#34C759', freshness: '#FFD60A' },
        gradeCopy: [
          'AI tools will confidently cite you in relevant searches.',
          'Good foundation. A few improvements will get you into AI results.',
          "You're building your AI presence. Keep going.",
          'Start with the quick wins below to get AI engines recognizing you.',
        ],
        shareText: (score, grade, url) => `My GEO Health Score is ${score}/100 (${grade}) on I'm On Social! Check out my digital card: ${url}`,
      }}
    />
  );
}
