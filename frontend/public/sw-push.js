/* Service Worker for Push Notifications */
self.addEventListener('push', function(event) {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch (e) {
    data = { title: 'On Social', body: event.data.text() };
  }

  const options = {
    body: data.body || '',
    icon: '/logo192.png',
    badge: '/favicon-32x32.png',
    data: { url: data.url || '/touchpoints/performance' },
    vibrate: [100, 50, 100],
    actions: [{ action: 'open', title: 'View' }],
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'On Social', options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = event.notification.data?.url || '/touchpoints/performance';
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        var client = clientList[i];
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});
