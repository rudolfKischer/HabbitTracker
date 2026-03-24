// Daily Tally — Service Worker
// Caches static assets permanently (cache-first).
// Caches HTML nav pages with network-first + fallback (enables offline + prefetch).

const STATIC_CACHE = 'tally-static-v1';
const PAGE_CACHE   = 'tally-pages-v1';

const STATIC_ASSETS = [
  '/static/style.css',
  '/static/manifest.json',
  '/static/apple-touch-icon.png',
  '/static/icon-192.png',
  '/static/icon-512.png',
];

const NAV_PAGES = ['/app', '/todos', '/trackers', '/schedule', '/stats', '/settings'];

// ── Install: pre-cache static assets ──
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(STATIC_CACHE)
      .then(c => c.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: delete old caches ──
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== STATIC_CACHE && k !== PAGE_CACHE)
            .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ──
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);

  // Static assets: cache-first, update in background
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.open(STATIC_CACHE).then(cache =>
        cache.match(e.request).then(cached => {
          const fresh = fetch(e.request).then(r => {
            if (r.ok) cache.put(e.request, r.clone());
            return r;
          });
          return cached || fresh;
        })
      )
    );
    return;
  }

  // Nav HTML pages: network-first, cache as fallback
  if (NAV_PAGES.includes(url.pathname) &&
      (e.request.headers.get('accept') || '').includes('text/html')) {
    e.respondWith(
      fetch(e.request)
        .then(r => {
          if (r.ok) {
            caches.open(PAGE_CACHE).then(c => c.put(e.request, r.clone()));
          }
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }
});
