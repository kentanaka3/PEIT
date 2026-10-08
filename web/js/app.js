/**
 * PEIT Main Web Application Entrypoint
 * Bootstraps router, stores, and custom elements
 */
import { store } from "./store.js";
import { PeitExtensionHost } from "./extensions/extension_host.js";
import "./components/activity_bar.js";
import "./components/data_grid.js";
import "./components/kpi_cards.js";
import "./components/status_bar.js";

let extensionHost = null;

async function initApp() {
  // Dynamically load Flutter Island custom element in isolation so any engine/asset
  // issue never halts the primary PEIT workbench bootstrap.
  import("./islands/flutter_island.js").catch((err) => {
    console.warn("Failed to dynamically load Flutter island component:", err);
  });
  // Initialize theme from store
  const currentTheme = store.getState().theme;
  document.documentElement.setAttribute("data-theme", currentTheme);

  // Setup theme button listener
  const themeToggle = document.getElementById("theme-toggle-btn");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      store.toggleTheme();
    });
  }

  // Setup banner retry listener
  const retryBtn = document.getElementById("banner-retry-btn");
  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      retryBtn.textContent = "Connecting...";
      store.init().finally(() => {
        retryBtn.textContent = "Retry Connection";
      });
    });
  }

  // Subscribe to state change for view switching and connection banner
  store.addEventListener("statechange", (e) => {
    const { selectedTab, online, isFallback, error } = e.detail;
    switchView(selectedTab);
    updateConnectionBanner(online, isFallback, error);
  });

  // Ensure initial view is visible immediately
  switchView(store.getState().selectedTab || "dashboard");

  // Load backend data (with graceful fallback handling)
  await store.init();

  // Initialize and load Extension Host
  extensionHost = new PeitExtensionHost({ store });
  await extensionHost.loadAllExtensions();
}

function updateConnectionBanner(online, isFallback, error) {
  const banner = document.getElementById("workbench-connection-banner");
  const msgEl = document.getElementById("banner-message");
  if (!banner || !msgEl) return;

  if (!online || isFallback) {
    banner.style.display = "flex";
    if (isFallback) {
      msgEl.innerHTML = `Daemon offline &mdash; displaying synthetic fallback data. Run <code class="mono">peit --serve</code> to connect to active ledger.`;
    } else {
      msgEl.innerHTML = `Unable to connect to synchronization daemon (${error || "offline"}).`;
    }
  } else {
    banner.style.display = "none";
  }
}

function switchView(tabId) {
  const standardViews = ["dashboard", "ledger", "flutter", "profiler"];
  const mainContent = document.getElementById("main-content");

  // Hide all standard views
  standardViews.forEach((v) => {
    const el = document.getElementById(`view-${v}`);
    if (el) {
      el.style.display = v === tabId ? "flex" : "none";
    }
  });

  // Handle dynamic extension views
  const dynamicViewPrefix = "view-ext-";
  let isDynamic = !standardViews.includes(tabId);

  // Hide all existing extension view containers
  if (mainContent) {
    const extContainers = mainContent.querySelectorAll(`[id^="${dynamicViewPrefix}"]`);
    extContainers.forEach((c) => {
      c.style.display = "none";
    });

    if (isDynamic) {
      let extViewContainer = document.getElementById(`${dynamicViewPrefix}${tabId}`);
      if (!extViewContainer) {
        extViewContainer = document.createElement("div");
        extViewContainer.id = `${dynamicViewPrefix}${tabId}`;
        extViewContainer.className = "main-view-container";
        // Create custom element tag matching tabId or registered view
        const customElName = `${tabId}-view`;
        extViewContainer.innerHTML = `<${customElName}></${customElName}>`;
        mainContent.appendChild(extViewContainer);
      }
      extViewContainer.style.display = "flex";
    }
  }

  const sidebarTitle = document.getElementById("sidebar-title");
  if (sidebarTitle) {
    const titles = {
      dashboard: "DASHBOARD OVERVIEW",
      ledger: "LEDGER EXPLORER",
      flutter: "MOBILE EMBEDDING",
      profiler: "MARKET PROFILER",
      "crypto-cpi": "CRYPTO CPI TERMINAL",
      "carbon-footprint": "ESG & CARBON FOOTPRINT",
    };
    sidebarTitle.textContent = titles[tabId] || tabId.toUpperCase().replace(/-/g, " ");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

