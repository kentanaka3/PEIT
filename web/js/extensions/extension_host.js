/**
 * PEIT Extension Host Runtime
 * Provides sandboxed execution context, lifecycle management,
 * and workbench contribution points for dynamic PEIT extensions.
 */

export class PeitExtensionHost {
  /**
   * @param {Object} options
   * @param {import("../store.js").PeitStore} options.store
   * @param {string} [options.registryUrl]
   */
  constructor({ store, registryUrl = "/extensions/manifest_registry.json" }) {
    this.store = store;
    this.registryUrl = registryUrl;
    this.registeredExtensions = new Map(); // id -> { manifest, module, context, activated: boolean }
    this.viewRegistry = new Map(); // viewId -> CustomElementClass
    this.statusBarRegistry = new Map(); // itemId -> { text, tooltip }
    this.eventListeners = new Map(); // eventName -> Set<callback>
  }

  /**
   * Initialize and load all registered extensions from the manifest registry.
   */
  async loadAllExtensions() {
    try {
      const res = await fetch(this.registryUrl);
      if (!res.ok) {
        console.warn(`[ExtensionHost] Could not load manifest registry from ${this.registryUrl}: HTTP ${res.status}`);
        return;
      }
      const data = await res.json();
      const extensions = Array.isArray(data.extensions) ? data.extensions : [];

      for (const extDef of extensions) {
        if (!extDef.enabled) {
          console.info(`[ExtensionHost] Skipping disabled extension: ${extDef.id}`);
          continue;
        }

        try {
          await this.loadExtension(extDef);
        } catch (err) {
          console.error(`[ExtensionHost] Error loading extension ${extDef.id}:`, err);
        }
      }
    } catch (err) {
      console.error("[ExtensionHost] Failed to initialize extension host:", err);
    }
  }

  /**
   * Load and activate a single extension.
   * @param {Object} extDef
   */
  async loadExtension(extDef) {
    const { id, manifest: manifestPath, entry: entryPath } = extDef;
    const manifestUrl = `/extensions/${manifestPath}`;
    const entryUrl = `/extensions/${entryPath}`;

    // 1. Fetch manifest
    const mRes = await fetch(manifestUrl);
    if (!mRes.ok) {
      throw new Error(`Failed to fetch manifest at ${manifestUrl} (HTTP ${mRes.status})`);
    }
    const manifest = await mRes.json();

    // 2. Process contributions (Activity Bar, StatusBar, Views)
    if (manifest.contributes?.activityBar) {
      const abItem = manifest.contributes.activityBar;
      window.dispatchEvent(
        new CustomEvent("peit:extension:activitybar:register", {
          detail: {
            id: abItem.id,
            title: abItem.title,
            icon: abItem.icon,
            extensionId: id,
          },
        })
      );
    }

    if (manifest.contributes?.statusBar) {
      for (const sbItem of manifest.contributes.statusBar) {
        this.statusBarRegistry.set(sbItem.id, {
          text: sbItem.text,
          tooltip: sbItem.tooltip || "",
        });
        window.dispatchEvent(
          new CustomEvent("peit:extension:statusbar:update", {
            detail: {
              id: sbItem.id,
              text: sbItem.text,
              tooltip: sbItem.tooltip,
            },
          })
        );
      }
    }

    // 3. Dynamically import entry ES module
    const mod = await import(entryUrl);
    const context = this.createExtensionContext(id, manifest);

    this.registeredExtensions.set(id, {
      manifest,
      module: mod,
      context,
      activated: false,
    });

    // 4. Activate extension
    await this.activateExtension(id);
  }

  /**
   * Create a least-privilege, frozen sandbox execution context.
   * @param {string} extensionId
   * @param {Object} manifest
   * @returns {Object}
   */
  createExtensionContext(extensionId, manifest) {
    const host = this;

    // Scoped Storage API
    const storageKeyPrefix = `peit:ext:${extensionId}:`;
    const storageApi = Object.freeze({
      get: (key, defaultValue = null) => {
        try {
          const val = localStorage.getItem(storageKeyPrefix + key);
          return val !== null ? JSON.parse(val) : defaultValue;
        } catch {
          return defaultValue;
        }
      },
      set: (key, value) => {
        try {
          localStorage.setItem(storageKeyPrefix + key, JSON.stringify(value));
        } catch (err) {
          console.warn(`[ExtensionHost:${extensionId}] Failed to set storage:`, err);
        }
      },
      remove: (key) => {
        localStorage.removeItem(storageKeyPrefix + key);
      },
    });

    // Scoped Ledger API
    const ledgerApi = Object.freeze({
      getEntries: (filter = null) => {
        const entries = host.store.getState().entries || [];
        if (!filter || typeof filter !== "function") {
          return [...entries];
        }
        return entries.filter(filter);
      },
      getSummary: () => {
        return host.store.getState().summary || null;
      },
      subscribeEntries: (callback) => {
        if (typeof callback !== "function") return () => {};
        const handler = (e) => {
          callback(e.detail?.entries || []);
        };
        host.store.addEventListener("statechange", handler);
        return () => host.store.removeEventListener("statechange", handler);
      },
    });

    // Scoped UI API
    const uiApi = Object.freeze({
      registerView: (viewId, customElementClass) => {
        host.viewRegistry.set(viewId, customElementClass);
        if (!customElements.get(viewId)) {
          customElements.define(viewId, customElementClass);
        }
        window.dispatchEvent(
          new CustomEvent("peit:extension:view:registered", {
            detail: { viewId, extensionId },
          })
        );
      },
      updateStatusBarItem: (itemId, text, tooltip = "") => {
        host.statusBarRegistry.set(itemId, { text, tooltip });
        window.dispatchEvent(
          new CustomEvent("peit:extension:statusbar:update", {
            detail: { id: itemId, text, tooltip },
          })
        );
      },
    });

    // Scoped Safe Pub/Sub Events API
    const eventsApi = Object.freeze({
      on: (eventName, callback) => {
        if (!host.eventListeners.has(eventName)) {
          host.eventListeners.set(eventName, new Set());
        }
        host.eventListeners.get(eventName).add(callback);
        return () => {
          host.eventListeners.get(eventName)?.delete(callback);
        };
      },
      emit: (eventName, payload) => {
        const listeners = host.eventListeners.get(eventName);
        if (listeners) {
          listeners.forEach((cb) => {
            try {
              cb(payload);
            } catch (err) {
              console.error(`[ExtensionHost] Listener error on '${eventName}':`, err);
            }
          });
        }
      },
    });

    return Object.freeze({
      extensionId,
      manifest: Object.freeze(JSON.parse(JSON.stringify(manifest))),
      ledger: ledgerApi,
      ui: uiApi,
      events: eventsApi,
      storage: storageApi,
    });
  }

  /**
   * Activate an extension by calling its activate(context) export.
   * @param {string} extensionId
   */
  async activateExtension(extensionId) {
    const ext = this.registeredExtensions.get(extensionId);
    if (!ext) return;
    if (ext.activated) return;

    try {
      if (typeof ext.module.activate === "function") {
        await ext.module.activate(ext.context);
      }
      ext.activated = true;
      console.info(`[ExtensionHost] Activated extension: ${extensionId}`);
    } catch (err) {
      console.error(`[ExtensionHost] Activation failed for ${extensionId}:`, err);
    }
  }

  /**
   * Deactivate an extension by calling its deactivate() export.
   * @param {string} extensionId
   */
  async deactivateExtension(extensionId) {
    const ext = this.registeredExtensions.get(extensionId);
    if (!ext || !ext.activated) return;

    try {
      if (typeof ext.module.deactivate === "function") {
        await ext.module.deactivate();
      }
      ext.activated = false;
      console.info(`[ExtensionHost] Deactivated extension: ${extensionId}`);
    } catch (err) {
      console.error(`[ExtensionHost] Deactivation failed for ${extensionId}:`, err);
    }
  }

  /**
   * Get custom element class for a view ID.
   * @param {string} viewId
   */
  getViewComponent(viewId) {
    return this.viewRegistry.get(viewId);
  }

  /**
   * Get all registered status bar items.
   */
  getStatusBarItems() {
    return Array.from(this.statusBarRegistry.entries()).map(([id, item]) => ({
      id,
      ...item,
    }));
  }
}

