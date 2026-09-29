/* nc-sync.js — Sauvegarde serveur du travail dans les outils (multi-appareils).
 *
 * La page-cadre (/tools/...) et l'outil (/toolfiles/...) sont SUR LE MÊME
 * DOMAINE → ils partagent localStorage + IndexedDB. Ce module (chargé par
 * tool_frame.html, donc côté NOUS → incassable aux updates de l'ami) :
 *   1. au chargement d'un outil : récupère le dernier instantané du serveur et
 *      le restaure dans le stockage AVANT que l'outil ne le lise (bootstrap),
 *   2. pendant l'usage : repousse le stockage vers le serveur (start).
 *
 * Robustesse : TOUT est sous try/catch. En cas de pépin réseau/sérialisation,
 * on n'empêche JAMAIS l'outil de fonctionner — on retombe sur le stockage local.
 *
 * Format d'instantané :
 *   { ls:{k:v,...}, idb:{ dbName:{ version, stores:{ storeName:{
 *       keyPath, autoIncrement, indexes:[{name,keyPath,unique,multiEntry}],
 *       records:[{k?,v}] } } } } }
 * Les Blob/ArrayBuffer/typed-arrays sont encodés base64 sous plafond
 * (NC_BLOB_CAP) — les gros médias bruts (vidéos d'avatar) sont volontairement
 * ignorés pour ne pas saturer (placeholder {__ncskipped}).
 */
(function () {
  "use strict";

  var MARKER     = "__nc_sync_version";   // version serveur que le local reflète
  var NC_BLOB_CAP = 2 * 1024 * 1024;      // plafond par blob synchronisé (2 Mo)
  var NC_TOTAL_CAP = 18 * 1024 * 1024;    // plafond total approx. de l'instantané
  var PUSH_INTERVAL = 60000;              // ms : vérif/push périodique
  var SKIP_LS = { };                      // clés localStorage à ne jamais synchro
  SKIP_LS[MARKER] = 1;

  var lastPushed = null;                  // dernière chaîne poussée (anti-spam)
  var totalBlobBytes = 0;                 // compteur pour NC_TOTAL_CAP

  function log(/*...*/) { try { /* console.debug.apply(console, arguments); */ } catch (e) {} }

  /* ---------- (dé)sérialisation valeurs structurées (blobs, etc.) ---------- */

  function abToB64(buf) {
    var bytes = new Uint8Array(buf), bin = "", chunk = 0x8000;
    for (var i = 0; i < bytes.length; i += chunk) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(bin);
  }
  function b64ToAb(b64) {
    var bin = atob(b64), len = bin.length, bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
    return bytes.buffer;
  }

  // Convertit une valeur (clonable IndexedDB) en JSON-able. Asynchrone à cause
  // des Blob (FileReader). Retourne une valeur enrichie de tags __nc*.
  function encodeValue(v) {
    if (v === null || typeof v !== "object") return Promise.resolve(v);

    if (v instanceof Blob) {
      if (v.size > NC_BLOB_CAP || totalBlobBytes + v.size > NC_TOTAL_CAP) {
        return Promise.resolve({ __ncskipped: true, size: v.size, type: v.type });
      }
      totalBlobBytes += v.size;
      return v.arrayBuffer().then(function (ab) {
        return { __ncblob: abToB64(ab), type: v.type || "", name: v.name || undefined };
      }).catch(function () { return { __ncskipped: true, size: v.size }; });
    }
    if (v instanceof ArrayBuffer) {
      if (v.byteLength > NC_BLOB_CAP || totalBlobBytes + v.byteLength > NC_TOTAL_CAP) {
        return Promise.resolve({ __ncskipped: true, size: v.byteLength });
      }
      totalBlobBytes += v.byteLength;
      return Promise.resolve({ __ncab: abToB64(v) });
    }
    if (ArrayBuffer.isView(v)) {            // typed array / DataView
      var buf = v.buffer;
      if (buf.byteLength > NC_BLOB_CAP || totalBlobBytes + buf.byteLength > NC_TOTAL_CAP) {
        return Promise.resolve({ __ncskipped: true, size: buf.byteLength });
      }
      totalBlobBytes += buf.byteLength;
      return Promise.resolve({ __ncta: abToB64(buf), ctor: v.constructor.name });
    }
    if (v instanceof Date) return Promise.resolve({ __ncdate: v.getTime() });

    if (Array.isArray(v)) {
      return Promise.all(v.map(encodeValue));
    }
    // objet simple : on encode chaque propriété
    var keys = Object.keys(v), out = {};
    return Promise.all(keys.map(function (k) {
      return encodeValue(v[k]).then(function (ev) { out[k] = ev; });
    })).then(function () { return out; });
  }

  function decodeValue(v) {
    if (v === null || typeof v !== "object") return v;
    if (v.__ncskipped) return null;                       // média ignoré → absent
    if (v.__ncblob !== undefined) return new Blob([b64ToAb(v.__ncblob)], { type: v.type || "" });
    if (v.__ncab   !== undefined) return b64ToAb(v.__ncab);
    if (v.__ncta   !== undefined) {
      var Ctor = window[v.ctor] || Uint8Array;
      try { return new Ctor(b64ToAb(v.__ncta)); } catch (e) { return b64ToAb(v.__ncta); }
    }
    if (v.__ncdate !== undefined) return new Date(v.__ncdate);
    if (Array.isArray(v)) return v.map(decodeValue);
    var out = {};
    Object.keys(v).forEach(function (k) { out[k] = decodeValue(v[k]); });
    return out;
  }

  /* ---------------------------- snapshot IDB ------------------------------ */

  function openDb(name, version) {
    return new Promise(function (resolve, reject) {
      var req = version ? indexedDB.open(name, version) : indexedDB.open(name);
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
      req.onblocked = function () { /* on attend */ };
    });
  }

  function readStore(db, storeName) {
    return new Promise(function (resolve) {
      var records = [];
      var tx, store;
      try { tx = db.transaction(storeName, "readonly"); store = tx.objectStore(storeName); }
      catch (e) { return resolve({ meta: null, records: [] }); }
      var meta = {
        keyPath: store.keyPath, autoIncrement: store.autoIncrement,
        indexes: [],
      };
      try {
        for (var i = 0; i < store.indexNames.length; i++) {
          var ix = store.index(store.indexNames[i]);
          meta.indexes.push({ name: ix.name, keyPath: ix.keyPath, unique: ix.unique, multiEntry: ix.multiEntry });
        }
      } catch (e) {}
      var cur = store.openCursor();
      var pending = [];
      cur.onsuccess = function (e) {
        var c = e.target.result;
        if (c) {
          var rec = { v: c.value };
          if (store.keyPath === null || store.keyPath === undefined) rec.k = c.key; // clé hors-ligne
          pending.push(encodeValue(c.value).then(function (recRef) {
            return function (ev) { recRef.v = ev; };
          }(rec)));
          records.push(rec);
          c.continue();
        } else {
          Promise.all(pending).then(function () { resolve({ meta: meta, records: records }); });
        }
      };
      cur.onerror = function () { resolve({ meta: meta, records: records }); };
    });
  }

  function snapshotIdb() {
    if (!indexedDB.databases) return Promise.resolve({});  // Firefox : pas d'énumération
    return indexedDB.databases().then(function (list) {
      var out = {};
      var chain = Promise.resolve();
      (list || []).forEach(function (info) {
        if (!info || !info.name) return;
        chain = chain.then(function () {
          return openDb(info.name).then(function (db) {
            var version = db.version, stores = {};
            var names = Array.prototype.slice.call(db.objectStoreNames);
            var p = Promise.resolve();
            names.forEach(function (sn) {
              p = p.then(function () {
                return readStore(db, sn).then(function (res) {
                  if (res.meta) stores[sn] = {
                    keyPath: res.meta.keyPath, autoIncrement: res.meta.autoIncrement,
                    indexes: res.meta.indexes, records: res.records,
                  };
                });
              });
            });
            return p.then(function () {
              db.close();
              out[info.name] = { version: version, stores: stores };
            });
          }).catch(function () { /* DB illisible → on saute */ });
        });
      });
      return chain.then(function () { return out; });
    }).catch(function () { return {}; });
  }

  function snapshotLs() {
    var out = {};
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (SKIP_LS[k]) continue;
        out[k] = localStorage.getItem(k);
      }
    } catch (e) {}
    return out;
  }

  function snapshot() {
    totalBlobBytes = 0;
    return snapshotIdb().then(function (idb) {
      return { ls: snapshotLs(), idb: idb };
    });
  }

  /* ---------------------------- restore IDB ------------------------------- */

  function deleteDb(name) {
    return new Promise(function (resolve) {
      var req = indexedDB.deleteDatabase(name);
      req.onsuccess = req.onerror = req.onblocked = function () { resolve(); };
    });
  }

  function restoreOneDb(name, spec) {
    // On recrée la base à neuf (schéma + index) puis on réinjecte les records.
    return deleteDb(name).then(function () {
      return new Promise(function (resolve) {
        var req = indexedDB.open(name, spec.version || 1);
        req.onupgradeneeded = function () {
          var db = req.result;
          Object.keys(spec.stores || {}).forEach(function (sn) {
            var st = spec.stores[sn];
            var opts = {};
            if (st.keyPath !== null && st.keyPath !== undefined) opts.keyPath = st.keyPath;
            if (st.autoIncrement) opts.autoIncrement = true;
            var os;
            try { os = db.createObjectStore(sn, opts); } catch (e) { return; }
            (st.indexes || []).forEach(function (ix) {
              try { os.createIndex(ix.name, ix.keyPath, { unique: ix.unique, multiEntry: ix.multiEntry }); }
              catch (e) {}
            });
          });
        };
        req.onsuccess = function () {
          var db = req.result;
          var storeNames = Object.keys(spec.stores || {});
          if (!storeNames.length) { db.close(); return resolve(); }
          var tx;
          try { tx = db.transaction(storeNames, "readwrite"); }
          catch (e) { db.close(); return resolve(); }
          storeNames.forEach(function (sn) {
            var st = spec.stores[sn], os;
            try { os = tx.objectStore(sn); } catch (e) { return; }
            (st.records || []).forEach(function (rec) {
              try {
                var val = decodeValue(rec.v);
                if (rec.k !== undefined) os.put(val, rec.k); else os.put(val);
              } catch (e) {}
            });
          });
          tx.oncomplete = function () { db.close(); resolve(); };
          tx.onerror = function () { db.close(); resolve(); };
          tx.onabort = function () { db.close(); resolve(); };
        };
        req.onerror = function () { resolve(); };
        req.onblocked = function () { /* attend */ };
      });
    });
  }

  function restore(snap) {
    if (!snap) return Promise.resolve();
    // localStorage
    try {
      var ls = snap.ls || {};
      // on retire les clés synchronisables absentes de l'instantané
      var existing = [];
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (!SKIP_LS[k]) existing.push(k);
      }
      existing.forEach(function (k) { if (!(k in ls)) try { localStorage.removeItem(k); } catch (e) {} });
      Object.keys(ls).forEach(function (k) { try { localStorage.setItem(k, ls[k]); } catch (e) {} });
    } catch (e) {}
    // IndexedDB
    var idb = snap.idb || {};
    var names = Object.keys(idb);
    var p = Promise.resolve();
    names.forEach(function (n) { p = p.then(function () { return restoreOneDb(n, idb[n]); }); });
    return p;
  }

  /* ------------------------------ réseau ---------------------------------- */

  function pull() {
    return fetch("/api/sync", { headers: { "Accept": "application/json" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function push(dataStr, baseVersion) {
    return fetch("/api/sync", {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ data: dataStr, base_version: baseVersion }),
    }).then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
      .catch(function () { return null; });
  }

  function localMarker() {
    try { var v = localStorage.getItem(MARKER); return v == null ? 0 : parseInt(v, 10) || 0; } catch (e) { return 0; }
  }
  function setMarker(v) { try { localStorage.setItem(MARKER, String(v)); } catch (e) {} }

  /* ------------------------------ API publique ---------------------------- */

  var NCSync = {
    // Avant de charger l'outil : si le serveur a une version plus récente que
    // ce que le local reflète, on restaure. Résout TOUJOURS (même en erreur).
    bootstrap: function () {
      return pull().then(function (server) {
        if (!server) return;
        var sv = server.version || 0;
        if (sv > 0 && sv > localMarker() && server.data) {
          var snap;
          try { snap = JSON.parse(server.data); } catch (e) { return; }
          return restore(snap).then(function () {
            setMarker(sv);
            lastPushed = server.data;
            log("[nc-sync] restauré v" + sv);
          });
        }
      }).catch(function () { /* jamais bloquer le chargement de l'outil */ });
    },

    // Pousse l'état courant si différent du dernier poussé.
    pushNow: function () {
      return snapshot().then(function (snap) {
        var dataStr;
        try { dataStr = JSON.stringify(snap); } catch (e) { return; }
        if (dataStr === lastPushed) return;                 // rien de neuf
        return push(dataStr, localMarker()).then(function (res) {
          if (!res) return;
          if (res.status === 200 && res.body && res.body.ok) {
            setMarker(res.body.version); lastPushed = dataStr;
            log("[nc-sync] poussé v" + res.body.version);
          } else if (res.status === 409 && res.body) {
            // Conflit : le serveur est plus récent. Un seul utilisateur → on
            // privilégie le travail en cours (force) mais on le signale.
            log("[nc-sync] conflit v" + res.body.version + " → push forcé");
            return push(dataStr, null).then(function (r2) {
              if (r2 && r2.body && r2.body.ok) { setMarker(r2.body.version); lastPushed = dataStr; }
            });
          }
        });
      }).catch(function () {});
    },

    // Démarre la sauvegarde périodique + à la fermeture/changement d'onglet.
    start: function () {
      var self = this;
      try { setInterval(function () { self.pushNow(); }, PUSH_INTERVAL); } catch (e) {}
      try {
        document.addEventListener("visibilitychange", function () {
          if (document.visibilityState === "hidden") self.pushNow();
        });
        window.addEventListener("pagehide", function () { self.pushNow(); });
      } catch (e) {}
    },
  };

  window.NCSync = NCSync;
})();
