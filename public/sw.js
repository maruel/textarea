// Bump on every change to a cached asset, else visitors keep the old version.
// See AGENTS.md.
const CACHE_NAME = 'textarea-2026-09-03'
const ASSETS = [
  '/',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName)
          }
        })
      )
    }).then(() => self.clients.claim())
  )
})

// Navigations go to the network first and refresh the cached copy, so a change
// to index.html ships on the next load. The cache is the offline fallback.
// Other assets stay cache first.
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const response = await fetch(event.request)
        if (response.ok) {
          const copy = response.clone()
          event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put('/', copy)))
        }
        return response
      } catch (e) {
        const cached = await caches.match('/')
        if (cached) return cached
        throw e
      }
    })())
    return
  }
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        return response || fetch(event.request)
      })
  )
})
