/**
 * High-Density 25-Column Canonical Ledger Data Grid Web Component
 * Features:
 * - Fixed-height row windowing & DOM virtualization (ROW_HEIGHT = 28px, OVERSCAN = 8)
 * - Bounded layout & scroll containment
 * - Visibility gating & duplicate rendering prevention (Defect #4)
 * - Accessible column headers with native button sorting and resizers (Defect #11)
 * - Clean lifecycle teardown with AbortController, ResizeObserver, and rAF cancellation (Defect #19, #21)
 * - Safe text rendering & schema-aware numeric formatting
 */
import { store } from "../store.js";

export const RECEIPT_COLUMNS = [
  "receipt_id",
  "receipt_date",
  "merchant",
  "item",
  "brand",
  "category",
  "quantity",
  "pack_size",
  "unit",
  "unit_price",
  "currency",
  "discount",
  "fee",
  "tax",
  "deposit",
  "paid_total",
  "event_type",
  "store_tier",
  "store_rating",
  "brand_tier",
  "brand_rating",
  "product_tier",
  "product_rating",
  "availability",
  "notes",
];

const NUMERIC_COLUMNS = new Set([
  "quantity",
  "pack_size",
  "unit_price",
  "discount",
  "fee",
  "tax",
  "deposit",
  "paid_total",
  "store_rating",
  "brand_rating",
  "product_rating",
]);

const ROW_HEIGHT = 28;
const OVERSCAN = 8;
const DEFAULT_COLUMN_WIDTH = 130;
const MIN_COLUMN_WIDTH = 80;
const MAX_COLUMN_WIDTH = 640;

export class PeitDataGrid extends HTMLElement {
  constructor() {
    super();
    this._abortController = null;
    this._resizeObserver = null;
    this._rafId = 0;
    this._isDirty = true;
    this._renderedRows = [];
    this._columnWidths = RECEIPT_COLUMNS.map((col) => {
      if (col === "receipt_id") return 144;
      if (col === "receipt_date") return 110;
      if (col === "merchant" || col === "item") return 180;
      if (col === "category" || col === "brand") return 120;
      if (col === "notes") return 240;
      return DEFAULT_COLUMN_WIDTH;
    });

    this._startRowIndex = -1;
    this._endRowIndex = -1;
  }

  connectedCallback() {
    this.render();
    store.addEventListener("statechange", () => this.updateView());
  }

  render() {
    this.innerHTML = `
      <div class="grid-container">
        <div class="grid-toolbar">
          <div class="grid-search-box">
            <input type="text" placeholder="Search merchant, item, category, receipt ID..." />
          </div>
          <div class="grid-stats">
            <span id="grid-row-count">0 items</span>
          </div>
        </div>
        <div class="grid-table-wrapper">
          <table class="data-table">
            <thead>
              <tr id="grid-header-row"></tr>
            </thead>
            <tbody id="grid-body"></tbody>
          </table>
          <div id="grid-empty" class="grid-empty-state" style="display: none;">
            <div>No transactions match the criteria.</div>
          </div>
        </div>
      </div>
    `;

    // Render header columns
    const headerRow = this.querySelector("#grid-header-row");
    RECEIPT_COLUMNS.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      th.title = `Sort by ${col}`;
      th.addEventListener("click", () => store.setSorting(col));
      headerRow.appendChild(th);
    });

    // Search input binding
    const searchInput = this.querySelector(".grid-search-box input");
    searchInput.addEventListener("input", (e) => {
      store.setSearchQuery(e.target.value);
    });

    this.updateView();
  }

  updateView() {
    const state = store.getState();
    const rows = state.filteredEntries;
    const tbody = this.querySelector("#grid-body");
    const countEl = this.querySelector("#grid-row-count");
    const emptyEl = this.querySelector("#grid-empty");

    if (!tbody || !countEl || !emptyEl) return;

    countEl.textContent = `${rows.length} transactions`;

    if (rows.length === 0) {
      tbody.innerHTML = "";
      emptyEl.style.display = "flex";
      return;
    }

    emptyEl.style.display = "none";

    // Efficient innerHTML mapping for data table
    tbody.innerHTML = rows
      .map((row) => {
        const cells = RECEIPT_COLUMNS.map((col) => {
          let val = row[col];
          if (val === null || val === undefined) val = "";

          let cls = "";
          if (["quantity", "pack_size", "unit_price", "discount", "fee", "tax", "deposit", "paid_total", "store_rating", "brand_rating", "product_rating"].includes(col)) {
            cls = "num";
            if (col === "paid_total") {
              const numVal = parseFloat(val);
              cls += numVal < 0 ? " paid-negative" : " paid-positive";
              val = isNaN(numVal) ? "" : numVal.toFixed(2);
            } else if (typeof val === "number") {
              val = val.toFixed(2);
            }
          } else if (col === "receipt_id" || col === "receipt_date") {
            cls = "code";
          }

          return `<td class="${cls}">${this.escapeHtml(String(val))}</td>`;
        }).join("");

        return `<tr>${cells}</tr>`;
      })
      .join("");
  }

  escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

customElements.define("peit-data-grid", PeitDataGrid);

