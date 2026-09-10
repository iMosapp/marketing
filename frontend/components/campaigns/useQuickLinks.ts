import { useEffect, useState } from 'react';
import api from '../../services/api';

export type QuickLink = { label: string; icon: string; color: string; url: string };
const APP_BASE = 'https://app.imonsocial.com';

// Tracked links a rep can drop into a touch with one tap (card, link page, showcase, store review links).
export function useQuickLinks(user: any): QuickLink[] {
  const [links, setLinks] = useState<QuickLink[]>([]);
  useEffect(() => {
    if (!user?._id) return;
    const base: QuickLink[] = [
      { label: 'Digital Card', icon: 'card-outline', color: '#C9A962', url: `${APP_BASE}/card/${user._id}` },
      { label: 'Link Page', icon: 'link-outline', color: '#007AFF', url: `${APP_BASE}/l/${user._id}` },
      { label: 'Showcase', icon: 'images-outline', color: '#34C759', url: `${APP_BASE}/showcase/${user._id}` },
    ];
    const storeId = user?.store_id;
    if (!storeId) { setLinks(base); return; }
    api.get(`/admin/stores/${storeId}`).then(r => {
      const rl = r.data?.review_links || {};
      const extra: QuickLink[] = [];
      if (rl.google) extra.push({ label: 'Google Review', icon: 'star-outline', color: '#FF9500', url: rl.google });
      if (rl.yelp) extra.push({ label: 'Yelp Review', icon: 'star-outline', color: '#D32323', url: rl.yelp });
      if (rl.facebook) extra.push({ label: 'FB Review', icon: 'logo-facebook', color: '#1877F2', url: rl.facebook });
      setLinks([...base, ...extra]);
    }).catch(() => setLinks(base));
  }, [user?._id]);
  return links;
}
