/**
 * Activity Bar Navigation Component
 */
import { store } from "../store.js";

export class PeitActivityBar extends HTMLElement {
  connectedCallback() {
    this.dynamicItems = [];
    this.render();
    store.addEventListener("statechange", () => this.updateActive());

    // Listen for extension activity bar contributions
    window.addEventListener("peit:extension:activitybar:register", (e) => {
      this.registerExtensionTab(e.detail);
    });
  }

  registerExtensionTab({ id, title, icon, extensionId }) {
    if (this.dynamicItems.some((item) => item.id === id)) return;
    this.dynamicItems.push({ id, title, icon, extensionId });
    this.render();
  }

  render() {
    const staticItemsHtml = `
      <button class="activity-item active" data-tab="dashboard" title="Dashboard & KPI Summary">
        <svg viewBox="0 0 24 24"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>
      </button>
      <button class="activity-item" data-tab="ledger" title="25-Column Canonical Ledger Grid">
        <svg viewBox="0 0 24 24"><path d="M4 3h16a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm0 4v3h16V7H4zm0 5v3h16v-3H4zm0 5v2h16v-2H4z"/></svg>
      </button>
      <button class="activity-item" data-tab="flutter" title="Mobile Stream & OCR Cropper (Flutter Island)">
        <svg viewBox="0 0 24 24"><path d="M17 1.01L7 1c-1.1 0-2 .9-2 2v18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V3c0-1.1-.9-1.99-2-1.99zM17 19H7V5h10v14z"/></svg>
      </button>
      <button class="activity-item" data-tab="profiler" title="Market Profiler & Econometrics">
        <svg viewBox="0 0 24 24"><path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/></svg>
      </button>
    `;

    const dynamicItemsHtml = this.dynamicItems
      .map(
        (item) => `
      <button class="activity-item" data-tab="${item.id}" title="${item.title}">
        ${item.icon}
      </button>
    `
      )
      .join("");

    this.innerHTML = staticItemsHtml + dynamicItemsHtml;

    this.querySelectorAll(".activity-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        store.setActiveTab(tab);
      });
    });

    this.updateActive();
  }

  updateActive() {
    const currentTab = store.getState().selectedTab;
    this.querySelectorAll(".activity-item").forEach((btn) => {
      if (btn.getAttribute("data-tab") === currentTab) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
  }
}

customElements.define("peit-activity-bar", PeitActivityBar);

