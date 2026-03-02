/**
 * FingerprintCache
 *
 * IndexedDB-backed cache for audio fingerprints.
 * Persists across browser sessions and prevents re-computation.
 */

import type { AudioFingerprint } from '../../types/domain';

/** Cache entry extends AudioFingerprint with persistence metadata */
interface CachedFingerprint extends AudioFingerprint {
  trackId: number;
  timestamp: number;
}

const DB_NAME = 'auralis-fingerprints';
const DB_VERSION = 1;
const STORE_NAME = 'fingerprints';

export class FingerprintCache {
  private db: IDBDatabase | null = null;
  private initPromise: Promise<void> | null = null;

  /**
   * Initialize the IndexedDB database.
   * Call this once before using the cache.
   */
  async init(): Promise<void> {
    // Reuse existing promise if already initializing
    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = new Promise((resolve, reject) => {
      // Skip if already initialized
      if (this.db) {
        resolve();
        return;
      }

      // Check for IndexedDB support
      if (!('indexedDB' in window)) {
        console.warn('IndexedDB not supported in this browser');
        resolve();
        return;
      }

      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => {
        console.error('Failed to open IndexedDB:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        console.log('FingerprintCache initialized');
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;

        // Create object store if not exists
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'trackId' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          console.log('Created FingerprintCache object store');
        }
      };
    });

    return this.initPromise;
  }

  /**
   * Get fingerprint from cache.
   * Returns null if not found or expired.
   */
  async get(trackId: number): Promise<AudioFingerprint | null> {
    await this.ensureInitialized();

    if (!this.db) {
      return null;
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(trackId);

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        const fingerprint = request.result as CachedFingerprint | undefined;

        if (!fingerprint) {
          resolve(null);
          return;
        }

        // Check if cache is expired (30 days)
        const CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;
        const now = Date.now();
        const isExpired = now - fingerprint.timestamp > CACHE_TTL_MS;

        if (isExpired) {
          // Delete expired entry
          this.delete(trackId).catch(console.error);
          resolve(null);
          return;
        }

        resolve(fingerprint);
      };
    });
  }

  /**
   * Store fingerprint in cache.
   */
  async set(trackId: number, fingerprint: Omit<AudioFingerprint, 'trackId'>): Promise<void> {
    await this.ensureInitialized();

    if (!this.db) {
      return;
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);

      const data: CachedFingerprint = {
        trackId,
        ...fingerprint,
        timestamp: Date.now(),
      };

      const request = store.put(data);

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        resolve();
      };
    });
  }

  /**
   * Check if fingerprint is cached.
   */
  async has(trackId: number): Promise<boolean> {
    const fingerprint = await this.get(trackId);
    return fingerprint !== null;
  }

  /**
   * Delete fingerprint from cache.
   */
  async delete(trackId: number): Promise<void> {
    await this.ensureInitialized();

    if (!this.db) {
      return;
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(trackId);

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        resolve();
      };
    });
  }

  /**
   * Clear all fingerprints from cache.
   */
  async clear(): Promise<void> {
    await this.ensureInitialized();

    if (!this.db) {
      return;
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        console.log('FingerprintCache cleared');
        resolve();
      };
    });
  }

  /**
   * Get all cached fingerprints.
   */
  async getAllKeys(): Promise<number[]> {
    await this.ensureInitialized();

    if (!this.db) {
      return [];
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAllKeys();

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        resolve((request.result as number[]) || []);
      };
    });
  }

  /**
   * Get cache size in bytes.
   */
  async getSize(): Promise<number> {
    await this.ensureInitialized();

    if (!this.db) {
      return 0;
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        const fingerprints = request.result as CachedFingerprint[];
        let totalSize = 0;

        for (const fp of fingerprints) {
          // Estimate size (rough calculation)
          totalSize += JSON.stringify(fp).length;
        }

        // Convert bytes to MB
        const sizeMB = totalSize / (1024 * 1024);
        resolve(sizeMB);
      };
    });
  }

  /**
   * Get cache statistics.
   */
  async getStats(): Promise<{
    total: number;
    sizeMB: number;
    oldestTimestamp: number | null;
    newestTimestamp: number | null;
  }> {
    await this.ensureInitialized();

    if (!this.db) {
      return {
        total: 0,
        sizeMB: 0,
        oldestTimestamp: null,
        newestTimestamp: null,
      };
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        const fingerprints = request.result as CachedFingerprint[];
        const sizeMB = fingerprints.reduce(
          (sum, fp) => sum + JSON.stringify(fp).length,
          0
        ) / (1024 * 1024);

        const timestamps = fingerprints.map(fp => fp.timestamp);
        const oldestTimestamp = timestamps.length > 0 ? Math.min(...timestamps) : null;
        const newestTimestamp = timestamps.length > 0 ? Math.max(...timestamps) : null;

        resolve({
          total: fingerprints.length,
          sizeMB,
          oldestTimestamp,
          newestTimestamp,
        });
      };
    });
  }

  /**
   * Clean up expired entries.
   */
  async cleanup(): Promise<number> {
    await this.ensureInitialized();

    if (!this.db) {
      return 0;
    }

    let deletedCount = 0;

    const keys = await this.getAllKeys();
    for (const key of keys) {
      const fp = await this.get(key);
      if (!fp) {
        // Already deleted by expiration check
        deletedCount++;
      }
    }

    console.log(`FingerprintCache cleanup: deleted ${deletedCount} expired entries`);
    return deletedCount;
  }

  /**
   * Ensure database is initialized before operations.
   */
  private async ensureInitialized(): Promise<void> {
    if (this.db) {
      return;
    }

    try {
      await this.init();
    } catch (err) {
      console.error('Failed to initialize FingerprintCache:', err);
    }
  }
}

// Create singleton instance
let cacheInstance: FingerprintCache | null = null;

/**
 * Get or create the fingerprint cache singleton.
 */
export function getFingerprintCache(): FingerprintCache {
  if (!cacheInstance) {
    cacheInstance = new FingerprintCache();
    // Initialize on first access
    cacheInstance.init().catch(err => {
      console.error('Failed to initialize FingerprintCache:', err);
    });
  }
  return cacheInstance;
}

/**
 * Reset the fingerprint cache singleton (for testing).
 */
export function resetFingerprintCache(): void {
  cacheInstance = null;
}
