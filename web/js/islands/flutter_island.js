/**
 * Flutter Element Embedding Island Container (<peit-flutter-island>)
 *
 * Implements:
 * 1. Dynamic initialization using _flutter.loader.load({ hostElement: ... })
 * 2. Graceful offline/development fallback when Flutter assets are not pre-built
 * 3. Loading state (spinner/progress indicator) & error boundary with retry button
 * 4. Bidirectional message passing between host ES module bus and Flutter instance
 *    via window CustomEvents ('peit:host:message', 'peit:island:message')
 * 5. Screen mode switching (Receipt Card Stream vs. KPI Dashboard)
 */
import { store } from "../store.js";

export class FlutterIsland extends HTMLElement {
  constructor() {
    super();
    this.status = "idle"; // 'idle' | 'loading' | 'running' | 'fallback' | 'error'
    this.errorMessage = null;
    this.currentIslandMode = "receipt_card_stream"; // 'receipt_card_stream' | 'dashboard'
    this.boundOnIslandMessage = this.handleIslandMessage.bind(this);
  }

  connectedCallback() {
    window.addEventListener("peit:island:message", this.boundOnIslandMessage);
    this.render();
  }

  disconnectedCallback() {
    window.removeEventListener("peit:island:message", this.boundOnIslandMessage);
  }

  render() {
    this.innerHTML = `
      <div id="flutter-island-container">
        <!-- Island Control Header -->
        <div class="island-header">
          <div style="font-weight: 600; font-size: 12px; display: flex; align-items: center; gap: 8px;">
            <svg style="width: 16px; height: 16px; fill: var(--md-sys-color-primary);" viewBox="0 0 24 24">
              <path d="M14.33 10l-4.46-4.46 4.46-4.46H18.5L14.04 5.54 18.5 10h-4.17zM9.87 14.46L5.41 10h4.17l4.46 4.46-4.46 4.46H5.41l4.46-4.46z"/>
            </svg>
            <span>Flutter Mobile Island</span>
            <span class="mono" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: var(--md-sys-color-surface-variant); color: var(--md-sys-color-on-surface-variant);">
              ${this.currentIslandMode === "dashboard" ? "KPI Dashboard" : "Card Stream"}
            </span>
          </div>

          <div style="display: flex; align-items: center; gap: 8px;">
            <div class="island-mode-selector" style="display: flex; gap: 4px; font-size: 11px;">
              <button id="btn-mode-stream" class="island-subtab-btn ${this.currentIslandMode === "receipt_card_stream" ? "active" : ""}" style="padding: 4px 8px; border-radius: 4px; border: 1px solid var(--md-sys-color-outline-variant); background: ${this.currentIslandMode === "receipt_card_stream" ? "var(--md-sys-color-primary)" : "transparent"}; color: ${this.currentIslandMode === "receipt_card_stream" ? "var(--md-sys-color-on-primary)" : "var(--md-sys-color-on-surface)"}; cursor: pointer;">
                Card Stream
              </button>
              <button id="btn-mode-dashboard" class="island-subtab-btn ${this.currentIslandMode === "dashboard" ? "active" : ""}" style="padding: 4px 8px; border-radius: 4px; border: 1px solid var(--md-sys-color-outline-variant); background: ${this.currentIslandMode === "dashboard" ? "var(--md-sys-color-primary)" : "transparent"}; color: ${this.currentIslandMode === "dashboard" ? "var(--md-sys-color-on-primary)" : "var(--md-sys-color-on-surface)"}; cursor: pointer;">
                Dashboard Screen
              </button>
            </div>
            <button id="btn-island-reload" title="Reload Island" style="padding: 4px 8px; border-radius: 4px; border: 1px solid var(--md-sys-color-outline-variant); background: transparent; color: var(--md-sys-color-outline); cursor: pointer; display: flex; align-items: center; gap: 4px; font-size: 11px;">
              <svg style="width: 12px; height: 12px; fill: currentColor;" viewBox="0 0 24 24">
                <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
              <span>Reload</span>
            </button>
          </div>
        </div>

        <!-- Island Mount Target Body -->
        <div class="island-body" id="flutter_receipt_island" style="width: 100%; height: calc(100% - 40px); display: flex; align-items: center; justify-content: center; position: relative;">
          ${this.renderBodyContent()}
        </div>
      </div>
    `;

    this.attachHeaderListeners();
  }

  renderBodyContent() {
    if (this.status === "loading") {
      return `
        <div class="island-loading-state" style="text-align: center; color: var(--md-sys-color-on-surface-variant); display: flex; flex-direction: column; align-items: center; gap: 12px;">
          <div class="island-spinner" style="width: 32px; height: 32px; border: 3px solid var(--md-sys-color-outline-variant); border-top-color: var(--md-sys-color-primary); border-radius: 50%; animation: island-spin 0.8s linear infinite;"></div>
          <div style="font-size: 13px; font-weight: 500;">Initializing Flutter Engine (CanvasKit/WASM)...</div>
          <div style="font-size: 11px; color: var(--md-sys-color-outline);" class="mono">Mounting target: #flutter_receipt_island</div>
        </div>
        <style>
          @keyframes island-spin {
            to { transform: rotate(360deg); }
          }
        </style>
      `;
    }

    if (this.status === "error") {
      return `
        <div class="island-error-state" style="text-align: center; color: var(--md-sys-color-on-surface); max-width: 440px; padding: 24px; border: 1px solid var(--peit-color-expense); border-radius: 8px; background: var(--md-sys-color-surface);">
          <div style="color: var(--peit-color-expense); margin-bottom: 8px;">
            <svg style="width: 36px; height: 36px; fill: currentColor;" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
          </div>
          <div style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">Flutter Island Failed to Load</div>
          <p style="font-size: 12px; color: var(--md-sys-color-outline); margin-bottom: 16px; line-height: 1.4;">
            ${this.errorMessage || "Unknown error occurred while initializing flutter.js engine."}
          </p>
          <button id="btn-island-retry" style="padding: 6px 16px; border-radius: 4px; background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border: none; font-size: 12px; font-weight: 600; cursor: pointer;">
            Retry Initialization
          </button>
        </div>
      `;
    }

    if (this.status === "running") {
      return ""; // Flutter canvas / DOM rendered inside #flutter_receipt_island
    }

    // Default / Fallback mode: preview sandbox when flutter.js is absent or in dev mode
    return `
      <div class="island-fallback-card" style="text-align: center; color: var(--md-sys-color-on-surface-variant); max-width: 480px; padding: 24px;">
        <div style="display: inline-flex; padding: 12px; border-radius: 50%; background: var(--md-sys-color-surface-container); margin-bottom: 12px;">
          <svg style="width: 28px; height: 28px; fill: var(--md-sys-color-primary);" viewBox="0 0 24 24">
            <path d="M14.33 10l-4.46-4.46 4.46-4.46H18.5L14.04 5.54 18.5 10h-4.17zM9.87 14.46L5.41 10h4.17l4.46 4.46-4.46 4.46H5.41l4.46-4.46z"/>
          </svg>
        </div>
        <div style="font-size: 15px; font-weight: 600; color: var(--md-sys-color-on-surface); margin-bottom: 6px;">
          Flutter Element Embedding Mount Ready
        </div>
        <p style="font-size: 12px; line-height: 1.5; color: var(--md-sys-color-outline); margin-bottom: 16px;">
          Host container <span class="mono">#flutter_receipt_island</span> is configured for
          <span class="mono">mobile/lib/screens/receipt_card_stream_screen.dart</span> and
          <span class="mono">dashboard_screen.dart</span> element embedding.
        </p>

        <div style="display: flex; justify-content: center; gap: 8px;">
          <button id="btn-island-launch" style="padding: 6px 16px; border-radius: 4px; background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border: none; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px;">
            <svg style="width: 14px; height: 14px; fill: currentColor;" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
            <span>Mount Flutter Island</span>
          </button>
          <button id="btn-send-sample" style="padding: 6px 12px; border-radius: 4px; background: transparent; color: var(--md-sys-color-outline); border: 1px solid var(--md-sys-color-outline-variant); font-size: 12px; cursor: pointer;">
            Test Host Bridge
          </button>
        </div>

        <div id="bridge-status-log" style="margin-top: 16px; font-size: 11px; color: var(--md-sys-color-on-surface-variant); text-align: left; background: var(--md-sys-color-surface-container); padding: 8px 12px; border-radius: 4px; border: 1px solid var(--md-sys-color-outline-variant); max-height: 80px; overflow-y: auto;" class="mono">
          Bridge: Ready for bidirectional messages.
        </div>
      </div>
    `;
  }

  attachHeaderListeners() {
    const btnStream = this.querySelector("#btn-mode-stream");
    if (btnStream) {
      btnStream.addEventListener("click", () => this.switchIslandMode("receipt_card_stream"));
    }

    const btnDashboard = this.querySelector("#btn-mode-dashboard");
    if (btnDashboard) {
      btnDashboard.addEventListener("click", () => this.switchIslandMode("dashboard"));
    }

    const btnReload = this.querySelector("#btn-island-reload");
    if (btnReload) {
      btnReload.addEventListener("click", () => this.loadFlutterEngine(true));
    }

    const btnLaunch = this.querySelector("#btn-island-launch");
    if (btnLaunch) {
      btnLaunch.addEventListener("click", () => this.loadFlutterEngine());
    }

    const btnRetry = this.querySelector("#btn-island-retry");
    if (btnRetry) {
      btnRetry.addEventListener("click", () => this.loadFlutterEngine(true));
    }

    const btnSample = this.querySelector("#btn-send-sample");
    if (btnSample) {
      btnSample.addEventListener("click", () => this.sendSampleCommand());
    }
  }

  switchIslandMode(mode) {
    if (this.currentIslandMode === mode) return;
    this.currentIslandMode = mode;
    this.logBridgeMessage(`Switched mode to ${mode}`);

    // If running, send route change command to Flutter island
    if (this.status === "running") {
      this.sendHostCommand("navigate_route", { mode });
    }
    this.render();
  }

  /**
   * Dynamically loads and initializes the Flutter Web engine via flutter.js element embedding.
   */
  async loadFlutterEngine(forceReload = false) {
    this.status = "loading";
    this.errorMessage = null;
    this.render();

    const hostEl = this.querySelector("#flutter_receipt_island");
    if (!hostEl) {
      this.status = "error";
      this.errorMessage = "Target host element #flutter_receipt_island not found in DOM.";
      this.render();
      return;
    }

    try {
      // 1. Check if flutter.js is present or needs injection
      if (!window._flutter) {
        await this.injectFlutterJsScript();
      }

      // 2. Initialize engine targeting our custom hostElement
      if (window._flutter && window._flutter.loader) {
        await window._flutter.loader.load({
          hostElement: hostEl,
          renderer: "canvaskit",
          initialRoute: `/?island=${this.currentIslandMode}`,
          onEntrypointLoaded: async (engineInitializer) => {
            const appRunner = await engineInitializer.initializeEngine({
              hostElement: hostEl,
              renderer: "canvaskit",
            });
            await appRunner.runApp();
            this.status = "running";
            this.logBridgeMessage("Flutter engine successfully mounted to island container.");
          },
        });
      } else {
        throw new Error("flutter.js loaded but _flutter.loader is unavailable.");
      }
    } catch (err) {
      console.warn("Flutter island dynamic load fallback:", err.message);
      this.status = "fallback";
      this.errorMessage = err.message;
      this.render();
      this.logBridgeMessage(`Offline/development mode: ${err.message}`);
    }
  }

  /**
   * Injects flutter.js script dynamically into document head.
   */
  injectFlutterJsScript() {
    return new Promise((resolve, reject) => {
      // Check if already injected
      const existingScript = document.querySelector('script[src*="flutter.js"]');
      if (existingScript) {
        resolve();
        return;
      }

      const script = document.createElement("script");
      script.src = "/flutter/flutter.js";
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => {
        reject(new Error("Compiled Flutter Web bundle (/flutter/flutter.js) not found. Run 'flutter build web' to compile assets."));
      };
      document.head.appendChild(script);
    });
  }

  /**
   * Bidirectional Host -> Flutter Command Dispatcher
   */
  sendHostCommand(action, data = {}) {
    const event = new CustomEvent("peit:host:message", {
      detail: {
        action,
        timestamp: new Date().toISOString(),
        data,
      },
    });
    window.dispatchEvent(event);
    this.logBridgeMessage(`Host -> Flutter [${action}]`);
  }

  /**
   * Bidirectional Flutter -> Host Message Handler
   */
  handleIslandMessage(e) {
    const detail = e.detail || {};
    const { action, data } = detail;
    this.logBridgeMessage(`Flutter -> Host [${action || "event"}]`);

    if (action === "entry_committed") {
      // Refresh entries in host reactive store
      store.fetchEntries();
      store.fetchSummary();
    } else if (action === "close_requested") {
      // Switch back to dashboard view
      store.setActiveTab("dashboard");
    }
  }

  sendSampleCommand() {
    this.sendHostCommand("ping", {
      message: "Hello from PEIT Vanilla Host Shell",
      mode: this.currentIslandMode,
    });
  }

  logBridgeMessage(msg) {
    const logEl = this.querySelector("#bridge-status-log");
    if (logEl) {
      const time = new Date().toLocaleTimeString();
      logEl.innerHTML = `[${time}] ${msg}<br/>` + logEl.innerHTML;
    }
  }
}

customElements.define("peit-flutter-island", FlutterIsland);
