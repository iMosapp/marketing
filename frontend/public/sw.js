// Service Worker for i'M On Social PWA — v4 (fixed offline fallback)
const CACHE_NAME = 'imos-v4';
const PRECACHE_URLS = [
  '/auth/login',
  '/cs-login',
  '/logo192.png',
  '/logo512.png',
  '/cs-logo-192.png',
  '/cs-logo-512.png',
  '/favicon.ico',
  '/apple-touch-icon.png',
  '/cs-apple-touch-icon.png',
  '/manifest.json',
  '/cs-manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Only intercept GET requests — let POST/PATCH/PUT/DELETE pass through untouched
  if (event.request.method !== 'GET') return;

  // Skip API calls entirely — never cache or intercept /api/ requests
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/api')) return;

  // For HTML pages — network-first, cache fallback
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cache successful navigation responses for offline fallback
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(async () => {
          // Network failed — try cache with proper async/await
          const isCS = url.pathname.includes('cs-login');
          const cached = await caches.match(event.request);
          if (cached) return cached;

          // Fallback to login page
          const fallback = isCS ? '/cs-login' : '/auth/login';
          const fallbackResponse = await caches.match(fallback);
          if (fallbackResponse) return fallbackResponse;

          // Nothing cached — return a simple offline page
          return new Response(
            '<html><body style="font-family:sans-serif;text-align:center;padding:60px"><h2>You appear to be offline</h2><p>Please check your connection and refresh.</p></body></html>',
            { headers: { 'Content-Type': 'text/html' } }
          );
        })
    );
    return;
  }

  // For static assets — network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        return cached || new Response('', { status: 408 });
      })
  );
});
