import { useEffect } from 'react';
import { useAuthStore } from '../../store/authStore';
import { useMediaTokenStore } from '../../store/mediaTokenStore';

// Keeps a fresh media token for the signed-in user (recordings / proxied media are fetched by URL); drops it on logout.
export const MediaTokenGate = () => {
  const userId = useAuthStore(s => s.user?._id as string | undefined);
  const ensure = useMediaTokenStore(s => s.ensure);
  const clear = useMediaTokenStore(s => s.clear);
  useEffect(() => {
    if (!userId) { clear(); return; }
    ensure(userId);
    const id = setInterval(() => ensure(userId), 10 * 60 * 1000);
    return () => clearInterval(id);
  }, [userId, ensure, clear]);
  return null;
};
