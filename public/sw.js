// Personal Share PWA - Service Worker
// Caching strategy:
//   /api/*      -> network-only
//   esm.sh CDN  -> cache-first
//   app shell   -> network-first with cache fallback

const CACHE_VERSION = '$SERVER_VERSION$';
const CDN_CACHE = 'share-cdn-v1';

const APP_SHELL_URLS = [
  '/',
  '/styles.css',
  '/manifest.json',
  '/js/app.js',
  '/js/store.js',
  '/js/items/ItemsView.js',
  '/js/items/ItemCard.js',
  '/js/items/NotesView.js',
  '/js/items/NoteCard.js',
  '/js/items/AddSheet.js',
  '/js/items/ContentViewer.js',
  '/js/items/ShareReceiver.js',
];

const CDN_URLS = [
  'https://esm.sh/preact@10.19.3',
  'https://esm.sh/preact@10.19.3/hooks',
  'https://esm.sh/@preact/signals@1.2.1?deps=preact@10.19.3',
  'https://esm.sh/htm@3.1.1',
  'https://esm.sh/localforage@1.10.0',
  'https://esm.sh/marked@15.0.7',
];

// ---------------------------------------------------------------------------
// Install
// ---------------------------------------------------------------------------
self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL_URLS)),
      caches.open(CDN_CACHE).then((cache) => cache.addAll(CDN_URLS)),
    ]).then(() => self.skipWaiting())
  );
});

// ---------------------------------------------------------------------------
// Activate
// ---------------------------------------------------------------------------
self.addEventListener('activate', (event) => {
  const keepCaches = new Set([CACHE_VERSION, CDN_CACHE]);
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => !keepCaches.has(name))
          .map((name) => caches.delete(name))
      )
    ).then(() => self.clients.claim())
  );
});

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API requests: network-only
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // CDN requests: cache-first
  if (url.hostname === 'esm.sh') {
    event.respondWith(cacheFirstCDN(request));
    return;
  }

  // App shell: network-first with cache fallback
  if (url.origin === self.location.origin) {
    event.respondWith(networkFirstAppShell(request));
  }
});

// ---------------------------------------------------------------------------
// Cache-first for CDN
// ---------------------------------------------------------------------------
async function cacheFirstCDN(request) {
  const cache = await caches.open(CDN_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

// ---------------------------------------------------------------------------
// Network-first for app shell
// ---------------------------------------------------------------------------
async function networkFirstAppShell(request) {
  const cache = await caches.open(CACHE_VERSION);

  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (_err) {
    const cacheUrl = new URL(request.url);
    cacheUrl.search = '';
    const cached = await cache.match(cacheUrl.href);
    if (cached) return cached;

    if (request.mode === 'navigate') {
      const fallback = await cache.match('/');
      if (fallback) return fallback;

      return new Response(
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">' +
        '<meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<title>Offline - Share</title>' +
        '<style>body{font-family:system-ui,sans-serif;display:flex;' +
        'align-items:center;justify-content:center;min-height:100vh;' +
        'margin:0;background:#1a1a2e;color:#e0e0e0;text-align:center}' +
        'h1{font-size:1.5rem;margin-bottom:.5rem}' +
        'p{color:#999;max-width:28ch}</style></head>' +
        '<body><div><h1>You are offline</h1>' +
        '<p>Check your connection and try again.</p></div></body></html>',
        { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
      );
    }

    return new Response('Network error', { status: 503 });
  }
}
