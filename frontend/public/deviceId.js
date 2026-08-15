/**
 * HOMEPOT shared device_id storage.
 *
 * Single source of truth for the persistent device identifier used by both
 * the main app (pushNotifications) and the service worker (push acks).
 *
 * IndexedDB is shared across all contexts of the same origin, so the page
 * and the service worker always resolve the same device_id.
 *
 * Loaded in the service worker via importScripts('/deviceId.js') and in the
 * page via <script src="/deviceId.js"></script> (see index.html).
 */
(function (global) {
  'use strict';

  var DB_NAME = 'homepot-db';
  var STORE_NAME = 'settings';
  var KEY = 'device_id';

  function generateUuid() {
    if (global.crypto && typeof global.crypto.randomUUID === 'function') {
      return global.crypto.randomUUID();
    }
    // Fallback for non-secure contexts where crypto.randomUUID is unavailable
    if (global.crypto && typeof global.crypto.getRandomValues === 'function') {
      var bytes = global.crypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      var hex = Array.prototype.map
        .call(bytes, function (b) {
          return (b < 16 ? '0' : '') + b.toString(16);
        })
        .join('');
      return (
        hex.slice(0, 8) +
        '-' +
        hex.slice(8, 12) +
        '-' +
        hex.slice(12, 16) +
        '-' +
        hex.slice(16, 20) +
        '-' +
        hex.slice(20)
      );
    }
    // Last resort fallback
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /**
   * Get or create the persistent device_id.
   * @returns {Promise<string>}
   */
  function getOrCreateDeviceId() {
    return new Promise(function (resolve, reject) {
      var request = global.indexedDB.open(DB_NAME, 1);

      request.onupgradeneeded = function (event) {
        var db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      };

      request.onsuccess = function (event) {
        var db = event.target.result;
        var transaction = db.transaction(STORE_NAME, 'readonly');
        var store = transaction.objectStore(STORE_NAME);
        var getRequest = store.get(KEY);

        getRequest.onsuccess = function () {
          if (getRequest.result) {
            resolve(getRequest.result);
          } else {
            var newId = generateUuid();
            var writeTransaction = db.transaction(STORE_NAME, 'readwrite');
            var writeStore = writeTransaction.objectStore(STORE_NAME);
            writeStore.put(newId, KEY);
            resolve(newId);
          }
        };

        getRequest.onerror = function () {
          reject(getRequest.error);
        };
      };

      request.onerror = function () {
        reject(request.error);
      };
    });
  }

  global.__HOMEPOT_DEVICE_ID__ = getOrCreateDeviceId;
})(typeof self !== 'undefined' ? self : globalThis);