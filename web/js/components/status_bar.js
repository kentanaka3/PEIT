/**
 * Workbench Status Bar Component
 */
import { store } from "../store.js";

export class PeitStatusBar extends HTMLElement {
  connectedCallback() {
    this.extensionItems = new Map();
    this.render();
    store.addEventListener("statechange", () => this.updateStatus());

    // Listen for extension statusbar updates
    window.addEventListener("peit:extension:statusbar:update", (e) => {
      this.handleExtensionStatus(e.detail);
    });
  }

  handleExtensionStatus({ id, text, tooltip }) {
    this.extensionItems.set(id, { text, tooltip });
    let itemEl = this.querySelector(`#ext-status-${id}`);
    if (!itemEl) {
      const rightContainer = this.querySelector(".status-right");
      if (rightContainer) {
        itemEl = document.createElement("div");
        itemEl.id = `ext-status-${id}`;
        itemEl.className = "status-item";
        rightContainer.prepend(itemEl);
      }
    }
    if (itemEl) {
      itemEl.textContent = text;
      if (tooltip) {
        itemEl.setAttribute("title", tooltip);
      }
    }
  }

  render() {
    this.innerHTML = `
      <div class="status-left">
        <div class="status-item">
          <span class="status-indicator status-online" id="status-daemon-dot"></span>
          <span id="status-daemon-text">Daemon Connected</span>
        </div>
        <div class="status-item mono" id="status-ledger-count">
          0 entries loaded
        </div>
      </div>
      <div class="status-right">
        <div class="status-item" id="status-pairing-indicator">
          <span>LAN Pairing: Idle</span>
        </div>
        <div class="status-item mono">
          <span>Schema v1 (25 cols)</span>
        </div>
      </div>
    `;

    // Re-render any existing extension items
    for (const [id, item] of this.extensionItems.entries()) {
      this.handleExtensionStatus({ id, ...item });
    }

    this.updateStatus();
  }

  updateStatus() {
    const state = store.getState();
    const dot = this.querySelector("#status-daemon-dot");
    const txt = this.querySelector("#status-daemon-text");
    const count = this.querySelector("#status-ledger-count");
    const pairing = this.querySelector("#status-pairing-indicator");

    if (!dot || !txt || !count || !pairing) return;

    if (state.online) {
      dot.className = "status-indicator status-online";
      txt.textContent = "Daemon Connected";
    } else {
      dot.className = "status-indicator status-offline";
      txt.textContent = "Daemon Offline";
    }

    if (state.health) {
      count.textContent = `${state.health.entry_count ?? 0} entries`;
      if (state.health.pairing_active) {
        dot.className = "status-indicator status-pairing";
        pairing.innerHTML = `<span style="color: var(--peit-color-rate-badge)">Pairing Mode Active</span>`;
      } else {
        pairing.textContent = "LAN Pairing: Idle";
      }
    }
  }
}

customElements.define("peit-status-bar", PeitStatusBar);

