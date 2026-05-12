const CACHE_NAME = 'family-tree-v1';
const STATIC_ASSETS = [
    '/',
    '/tree',
    '/static/manifest.json',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    // можно добавить другие часто используемые ресурсы
];

// Установка и кеширование статики
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
});

// Стратегия "сеть сначала, при неудаче – кеш"
self.addEventListener('fetch', event => {
    // Не кешируем POST-запросы и API
    if (event.request.method !== 'GET') {
        return;
    }
    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Кешируем успешные ответы
                if (response && response.status === 200) {
                    const clonedResponse = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, clonedResponse);
                    });
                }
                return response;
            })
            .catch(() => {
                // Если сеть недоступна, отдаём из кеша
                return caches.match(event.request);
            })
    );
});

// Удаление старых кешей при активации
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(name => name !== CACHE_NAME)
                          .map(name => caches.delete(name))
            );
        })
    );
});