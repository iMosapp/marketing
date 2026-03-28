// Service Worker for i'M On Social PWA — v5 (minimal, safe)
// Strategy: NEVER intercept page navigation. Only passively cache static assets.
// This prevents the service worker from ever breaking page loads.
const CACHE_NAME = 'imos-v5';

self.addEventListener('install', (event) => {
  // Skip waiting — take control immediately
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Clean up ALL old caches from previous versions
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // ONLY intercept GET requests for static assets (images, fonts, JS, CSS)
  // NEVER touch navigation, API calls, or HTML pages
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Never intercept: API calls, HTML navigation, fix page
  if (url.pathname.startsWith('/api')) return;
  if (event.request.mode === 'navigate') return;
  if (event.request.headers.get('accept')?.includes('text/html')) return;

  // Only cache static assets (images, icons, manifests)
  const isStaticAsset = /\.(png|jpg|jpeg|webp|ico|svg|json|woff2?)$/i.test(url.pathname);
  if (!isStaticAsset) return;

  // Stale-while-revalidate for static assets only
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached);

      return cached || fetchPromise;
    })
  );
});

// Push notification support
self.addEventListener('push', (event) => {
  try {
    const data = event.data ? event.data.json() : {};
    const title = data.title || "i'M On Social";
    const options = {
      body: data.body || '',
      icon: '/logo192.png',
      badge: '/logo192.png',
      data: data.url ? { url: data.url } : {},
    };
    event.waitUntil(self.registration.showNotification(title, options));
  } catch (e) {
    // Silent fail — never crash the service worker
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(clients.openWindow(url));
});
