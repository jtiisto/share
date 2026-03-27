// Personal Share PWA - Service Worker
// Caching strategy:
//   /api/*      -> network-only (with offline share queuing)
//   esm.sh CDN  -> cache-first
//   app shell   -> network-first with cache fallback

const CACHE_VERSION = '$SERVER_VERSION$';
const CDN_CACHE = 'share-cdn-v1';
const SHARE_QUEUE_STORE = 'share-offline-queue';
const B = '$BASE_PATH$';

const APP_SHELL_URLS = [
  B + '/',
  B + '/styles.css',
  B + '/manifest.json',
  B + '/js/app.js',
  B + '/js/store.js',
  B + '/js/items/ItemsView.js',
  B + '/js/items/ItemCard.js',
  B + '/js/items/NotesView.js',
  B + '/js/items/NoteCard.js',
  B + '/js/items/AddSheet.js',
  B + '/js/items/ContentViewer.js',
  B + '/js/items/ShareReceiver.js',
  B + '/js/items/CategoryPicker.js',
  B + '/js/items/FoldersView.js',
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
// IndexedDB helpers for offline share queue
// ---------------------------------------------------------------------------
function openQueueDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(SHARE_QUEUE_STORE, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore('queue', { autoIncrement: true });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function enqueueShare(data) {
  // data may contain { title, text, url, fileName, fileType, fileBlob }
  const db = await openQueueDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('queue', 'readwrite');
    tx.objectStore('queue').add(data);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function drainShareQueue() {
  const db = await openQueueDB();
  const items = await new Promise((resolve, reject) => {
    const tx = db.transaction('queue', 'readonly');
    const req = tx.objectStore('queue').getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });

  if (items.length === 0) return;

  for (const entry of items) {
    try {
      const form = new FormData();
      if (entry.title) form.append('title', entry.title);
      if (entry.text) form.append('text', entry.text);
      if (entry.url) form.append('url', entry.url);
      if (entry.fileBlob) {
        form.append('file', new File([entry.fileBlob], entry.fileName || 'shared_file', {
          type: entry.fileType || 'application/octet-stream'
        }));
      }
      await fetch(B + '/api/share', { method: 'POST', body: form });
    } catch {
      // If still offline, stop trying
      return;
    }
  }

  // Clear the queue
  const tx = db.transaction('queue', 'readwrite');
  tx.objectStore('queue').clear();
}

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

  // Intercept share target POST to app URL — the browser POSTs FormData here
  // when the user shares content (text, URLs, or files) from another Android app.
  // We extract the data, forward it to the backend API, and redirect to the app.
  if ((url.pathname === B + '/' || url.pathname === B) && request.method === 'POST') {
    event.respondWith(handleShareTargetPost(request));
    return;
  }

  // Intercept POST /share/api/share when offline — queue for later
  if (url.pathname === B + '/api/share' && request.method === 'POST') {
    event.respondWith(handleShareRequest(request));
    return;
  }

  // Other API requests: network-only
  if (url.pathname.startsWith(B + '/api/')) {
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
// Handle share target POST (from Android share intent via manifest share_target)
// The browser POSTs multipart FormData to the action URL. We forward it to the
// backend API and redirect the user to the app with a result query param.
// ---------------------------------------------------------------------------
async function handleShareTargetPost(request) {
  try {
    const formData = await request.formData();

    // Build a new FormData to forward to the backend API
    const apiForm = new FormData();
    const title = formData.get('title');
    const text = formData.get('text');
    const url = formData.get('url');
    const file = formData.get('file');

    if (title) apiForm.append('title', title);
    if (text) apiForm.append('text', text);
    if (url) apiForm.append('url', url);
    if (file && file instanceof File && file.size > 0) {
      apiForm.append('file', file, file.name);
    }

    try {
      const resp = await fetch(B + '/api/share', { method: 'POST', body: apiForm });
      if (resp.ok) {
        return Response.redirect(B + '/?shared=success', 303);
      }
      return Response.redirect(B + '/?shared=error', 303);
    } catch {
      // Offline — queue for later (including file blob if present)
      const queueData = {};
      if (title) queueData.title = title;
      if (text) queueData.text = text;
      if (url) queueData.url = url;
      if (file && file instanceof File && file.size > 0) {
        queueData.fileBlob = await file.arrayBuffer();
        queueData.fileName = file.name;
        queueData.fileType = file.type;
      }
      if (Object.keys(queueData).length > 0) {
        await enqueueShare(queueData);
      }
      return Response.redirect(B + '/?shared=queued', 303);
    }
  } catch {
    return Response.redirect(B + '/?shared=error', 303);
  }
}

// ---------------------------------------------------------------------------
// Handle share requests (with offline fallback)
// ---------------------------------------------------------------------------
async function handleShareRequest(request) {
  try {
    const response = await fetch(request.clone());
    return response;
  } catch (_err) {
    // Offline: extract form data and queue it
    try {
      const formData = await request.formData();
      const data = {};
      for (const [key, value] of formData.entries()) {
        if (typeof value === 'string') {
          data[key] = value;
        }
        // Note: file shares can't be queued easily, only text/url
      }
      if (data.title || data.text || data.url) {
        await enqueueShare(data);
      }
    } catch {
      // formData parsing failed
    }

    return new Response(
      JSON.stringify({ queued: true, message: 'Saved offline, will sync when back online' }),
      { status: 202, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// ---------------------------------------------------------------------------
// Drain queue when coming back online
// ---------------------------------------------------------------------------
self.addEventListener('message', (event) => {
  if (event.data === 'drain-share-queue') {
    drainShareQueue();
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
      const fallback = await cache.match(B + '/');
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
