/**
 * IndexedDB-based Client-Side Cache for Timeseries Data
 * ======================================================
 *
 * Canonical Source: [CS-008] MDN IndexedDB - "IndexedDB optimal for large
 * structured datasets with indexes"
 *
 * Purpose: Enable instant resolution switching (<100ms) by caching timeseries
 * data locally. When user switches from 1h back to 5m, the 5m data loads
 * instantly from IndexedDB without a network request.
 *
 * Schema Version: 2.0.0 (increment on breaking changes)
 * TTLs: Resolution-dependent [CS-013, CS-014]
 *   - 1m: 6 hours
 *   - 5m: 12 hours
 *   - 1h: 7 days
 *   - 24h: 90 days
 */

const CACHE_DB_NAME = 'sentiment-timeseries-cache';
const CACHE_STORE_NAME = 'timeseries';
const CACHE_VERSION = 2;  // Increment on schema changes
const CACHE_VERSION_KEY = 'timeseries_cache_version';

/**
 * Resolution-dependent TTLs in milliseconds [CS-013, CS-014]
 */
const RESOLUTION_TTL_MS = {
    '1m':  6 * 60 * 60 * 1000,       // 6 hours
    '5m':  12 * 60 * 60 * 1000,      // 12 hours
    '10m': 12 * 60 * 60 * 1000,      // 12 hours
    '1h':  7 * 24 * 60 * 60 * 1000,  // 7 days
    '3h':  14 * 24 * 60 * 60 * 1000, // 14 days
    '6h':  30 * 24 * 60 * 60 * 1000, // 30 days
    '12h': 60 * 24 * 60 * 60 * 1000, // 60 days
    '24h': 90 * 24 * 60 * 60 * 1000  // 90 days
};

/**
 * TimeseriesCache - IndexedDB wrapper for timeseries data
 */
class TimeseriesCache {
    constructor() {
        this.db = null;
        this.stats = {
            hits: 0,
            misses: 0
        };
    }

    /**
     * Initialize the cache database
     * Checks version and clears if schema changed
     */
    async init() {
        // Check for version mismatch and clear if needed
        const storedVersion = localStorage.getItem(CACHE_VERSION_KEY);
        if (storedVersion !== String(CACHE_VERSION)) {
            console.log(`Cache version changed from ${storedVersion} to ${CACHE_VERSION}, clearing cache`);
            await this.clear();
            localStorage.setItem(CACHE_VERSION_KEY, String(CACHE_VERSION));
        }

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(CACHE_DB_NAME, CACHE_VERSION);

            request.onerror = () => {
                console.error('Failed to open IndexedDB:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                console.log('IndexedDB cache initialized');
                resolve(this);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Delete old store if exists
                if (db.objectStoreNames.contains(CACHE_STORE_NAME)) {
                    db.deleteObjectStore(CACHE_STORE_NAME);
                }

                // Create new store with compound key
                const store = db.createObjectStore(CACHE_STORE_NAME, {
                    keyPath: ['ticker', 'resolution', 'bucketKey']
                });

                // Index for efficient ticker+resolution queries
                store.createIndex('ticker_resolution', ['ticker', 'resolution'], { unique: false });

                // Index for TTL cleanup
                store.createIndex('expires_at', 'expiresAt', { unique: false });

                console.log('IndexedDB store created');
            };
        });
    }

    /**
     * Generate cache key for a timeseries bucket
     */
    _makeBucketKey(ticker, resolution, bucketTimestamp) {
        return `${ticker}#${resolution}#${bucketTimestamp}`;
    }

    /**
     * Get cached data for a ticker+resolution
     * Returns null if not found or expired
     *
     * @param {string} ticker - e.g., "AAPL"
     * @param {string} resolution - e.g., "5m"
     * @param {string} [startTime] - ISO timestamp for range query
     * @param {string} [endTime] - ISO timestamp for range query
     * @returns {Promise<Array|null>} Cached buckets or null
     */
    async get(ticker, resolution, startTime = null, endTime = null) {
        if (!this.db) {
            await this.init();
        }

        return new Promise((resolve) => {
            const transaction = this.db.transaction(CACHE_STORE_NAME, 'readonly');
            const store = transaction.objectStore(CACHE_STORE_NAME);
            const index = store.index('ticker_resolution');

            const now = Date.now();
            const results = [];

            const request = index.openCursor(IDBKeyRange.only([ticker, resolution]));

            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    const record = cursor.value;

                    // Check if expired
                    if (record.expiresAt > now) {
                        // Apply time range filter if specified
                        const bucketTime = new Date(record.bucketTimestamp).getTime();
                        const start = startTime ? new Date(startTime).getTime() : 0;
                        const end = endTime ? new Date(endTime).getTime() : Infinity;

                        if (bucketTime >= start && bucketTime <= end) {
                            results.push(record.data);
                        }
                    }
                    cursor.continue();
                } else {
                    // Cursor exhausted
                    if (results.length > 0) {
                        this.stats.hits++;
                        // Sort by bucket timestamp
                        results.sort((a, b) => {
                            const timeA = new Date(a.bucket_timestamp || a.SK).getTime();
                            const timeB = new Date(b.bucket_timestamp || b.SK).getTime();
                            return timeA - timeB;
                        });
                        resolve(results);
                    } else {
                        this.stats.misses++;
                        resolve(null);
                    }
                }
            };

            request.onerror = () => {
                console.error('Cache get failed:', request.error);
                this.stats.misses++;
                resolve(null);
            };
        });
    }

    /**
     * Store timeseries data in cache
     *
     * @param {string} ticker - e.g., "AAPL"
     * @param {string} resolution - e.g., "5m"
     * @param {Array} buckets - Array of bucket objects from API
     */
    async set(ticker, resolution, buckets) {
        if (!this.db) {
            await this.init();
        }

        const ttlMs = RESOLUTION_TTL_MS[resolution] || RESOLUTION_TTL_MS['1h'];
        const expiresAt = Date.now() + ttlMs;

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(CACHE_STORE_NAME, 'readwrite');
            const store = transaction.objectStore(CACHE_STORE_NAME);

            let completed = 0;
            let errors = 0;

            buckets.forEach((bucket) => {
                const bucketTimestamp = bucket.bucket_timestamp || bucket.SK;
                const bucketKey = this._makeBucketKey(ticker, resolution, bucketTimestamp);

                const record = {
                    ticker,
                    resolution,
                    bucketKey,
                    bucketTimestamp,
                    data: bucket,
                    expiresAt,
                    cachedAt: Date.now()
                };

                const request = store.put(record);
                request.onsuccess = () => {
                    completed++;
                    if (completed + errors === buckets.length) {
                        resolve({ stored: completed, errors });
                    }
                };
                request.onerror = () => {
                    errors++;
                    console.error('Failed to cache bucket:', request.error);
                    if (completed + errors === buckets.length) {
                        resolve({ stored: completed, errors });
                    }
                };
            });

            // Handle empty buckets array
            if (buckets.length === 0) {
                resolve({ stored: 0, errors: 0 });
            }
        });
    }

    /**
     * Remove expired entries from cache
     */
    async cleanup() {
        if (!this.db) {
            await this.init();
        }

        return new Promise((resolve) => {
            const transaction = this.db.transaction(CACHE_STORE_NAME, 'readwrite');
            const store = transaction.objectStore(CACHE_STORE_NAME);
            const index = store.index('expires_at');

            const now = Date.now();
            let deleted = 0;

            // Find all expired entries
            const request = index.openCursor(IDBKeyRange.upperBound(now));

            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    store.delete(cursor.primaryKey);
                    deleted++;
                    cursor.continue();
                } else {
                    console.log(`Cache cleanup: removed ${deleted} expired entries`);
                    resolve(deleted);
                }
            };

            request.onerror = () => {
                console.error('Cache cleanup failed:', request.error);
                resolve(0);
            };
        });
    }

    /**
     * Clear all cached data
     */
    async clear() {
        return new Promise((resolve) => {
            const request = indexedDB.deleteDatabase(CACHE_DB_NAME);
            request.onsuccess = () => {
                this.db = null;
                this.stats = { hits: 0, misses: 0 };
                console.log('Cache cleared');
                resolve();
            };
            request.onerror = () => {
                console.error('Failed to clear cache:', request.error);
                resolve();
            };
        });
    }

    /**
     * Get cache statistics
     */
    getStats() {
        const total = this.stats.hits + this.stats.misses;
        return {
            hits: this.stats.hits,
            misses: this.stats.misses,
            hitRate: total > 0 ? this.stats.hits / total : 0
        };
    }

    /**
     * Check if cache has data for ticker+resolution
     */
    async has(ticker, resolution) {
        const data = await this.get(ticker, resolution);
        return data !== null && data.length > 0;
    }
}

// Export singleton instance
const timeseriesCache = new TimeseriesCache();

// Run cleanup periodically (every 5 minutes)
setInterval(() => {
    timeseriesCache.cleanup().catch(console.error);
}, 5 * 60 * 1000);

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TimeseriesCache, timeseriesCache, RESOLUTION_TTL_MS };
}
