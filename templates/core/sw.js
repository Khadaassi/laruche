// Service worker de La Ruche (servi par Django à /sw.js).
// - Fichiers statiques : cache d'abord (ils sont versionnés par WhiteNoise).
// - Pages : toujours le réseau ; hors connexion, page « Hors connexion ».
//   Les pages ne sont pas mises en cache (données privées de la famille), SAUF la
//   page « En magasin » (STORE_URL) : réseau d'abord, dernière copie si le réseau
//   manque, pour cocher sans réseau au magasin. Cette copie (cache PRIVATE) est
//   effacée dès qu'on arrive sur la page de connexion (déconnexion, session expirée).
// - Notifications push : affichage et ouverture de la bonne page.
const VERSION = 'laruche-v2';
const PRIVATE = 'laruche-private';
const OFFLINE_URL = '{{ offline_url }}';
const STORE_URL = '{{ store_url }}';
const LOGIN_URL = '{{ login_url }}';
const PRECACHE = [OFFLINE_URL, '{{ app_css }}'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION && k !== PRIVATE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(request, copy));
        }
        return response;
      })),
    );
    return;
  }
  if (url.pathname === STORE_URL) {
    event.respondWith(storePage(request));
    return;
  }
  if (request.mode === 'navigate') {
    if (url.pathname === LOGIN_URL) event.waitUntil(caches.delete(PRIVATE));
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
  }
});

// Page « En magasin » : réseau d'abord ; copie gardée seulement si c'est bien la page
// (pas une redirection vers la connexion) ; sans réseau, la dernière copie.
async function storePage(request) {
  try {
    const response = await fetch(request);
    if (response.ok && !response.redirected) {
      const cache = await caches.open(PRIVATE);
      await cache.put(STORE_URL, response.clone());
    } else if (response.redirected) {
      await caches.delete(PRIVATE);
    }
    return response;
  } catch (error) {
    const copy = await caches.match(STORE_URL, { cacheName: PRIVATE });
    return copy || (request.mode === 'navigate' ? caches.match(OFFLINE_URL) : Response.error());
  }
}

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (error) { data = { body: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(data.title || 'La Ruche', {
    body: data.body || '',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    tag: data.tag || undefined,
    data: { url: data.url || '/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const client of list) {
      if ('focus' in client) { client.navigate(target); return client.focus(); }
    }
    return self.clients.openWindow(target);
  }));
});
