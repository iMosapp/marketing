import React from 'react';
import { HealthScoreScreen } from '../components/health/HealthScoreScreen';

export default function SEOHealthScreen() {
  return (
    <HealthScoreScreen
      config={{
        kind: 'seo',
        title: 'SEO Health',
        guideRoute: '/seo-guide',
        factorIcons: { profile: 'person-circle', reviews: 'star', distribution: 'share-social', visibility: 'search', freshness: 'flash' },
        factorColors: { profile: '#C9A962', reviews: '#FFD60A', distribution: '#AF52DE', visibility: '#34C759', freshness: '#FF9500' },
        gradeCopy: [
          'Your SEO presence is outstanding.',
          'Good foundation. A few improvements will make a big difference.',
          "You're on the right track. Focus on the tips below to grow.",
          "Let's build your online presence. Start with the quick wins below.",
        ],
        shareText: (score, grade, url) => `My SEO Health Score is ${score}/100 (${grade}) on I'm On Social! Check out my digital card: ${url}`,
      }}
    />
  );
}
