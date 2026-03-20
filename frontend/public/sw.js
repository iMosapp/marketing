// Service Worker for i'M On Social PWA — v3 (Calendar Systems support)
const CACHE_NAME = 'imos-v3';
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
  if (event.request.method !== 'GET') return;

  // For HTML pages — always go network-first to ensure latest meta tags
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        // Check if this is a CS-branded request
        const url = new URL(event.request.url);
        if (url.pathname.includes('cs-login')) {
          return caches.match('/cs-login') || caches.match(event.request);
        }
        return caches.match(event.request) || caches.match('/auth/login');
      })
    );
    return;
  }

  // For assets — network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
