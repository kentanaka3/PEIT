/**
 * KPI Cards Component
 * Renders cash flow cards, net balance, and inflation index metrics
 * strictly matching canonical price index definitions in src/peit/core.py.
 */
import { store } from "../store.js";

export class PeitKpiCards extends HTMLElement {
  connectedCallback() {
    this._abortController = new AbortController();
    this.render();
    store.addEventListener("statechange", () => this.updateValues(), {
      signal: this._abortController.signal,
    });
  }

  disconnectedCallback() {
    if (this._abortController) {
      this._abortController.abort();
      this._abortController = null;
    }
  }

  render() {
    this.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-title">Net Balance</div>
          <div class="kpi-value" id="kpi-net-balance">$0.00</div>
          <div class="kpi-subtitle">Authoritative monthly net position</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">Total Expenditure</div>
          <div class="kpi-value expense" id="kpi-expenditure">$0.00</div>
          <div class="kpi-subtitle">Outflows & consumption purchases</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">Total Income</div>
          <div class="kpi-value income" id="kpi-income">$0.00</div>
          <div class="kpi-subtitle">Inflows & wages</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">Price Change Index</div>
          <div class="kpi-value" id="kpi-index">
            <span class="kpi-badge badge-neutral" id="kpi-index-badge">Unavailable</span>
          </div>
          <div class="kpi-subtitle" id="kpi-index-subtitle">Fixed Basket Base = 100.0</div>
        </div>
      </div>
    `;

    this.updateValues();
  }

  updateValues() {
    const state = store.getState();
    const summary = state.summary;
    if (!summary) return;

    const netBalEl = this.querySelector("#kpi-net-balance");
    const expEl = this.querySelector("#kpi-expenditure");
    const incEl = this.querySelector("#kpi-income");
    const idxBadge = this.querySelector("#kpi-index-badge");
    const idxSubtitle = this.querySelector("#kpi-index-subtitle");

    if (netBalEl) {
      const net = Number(summary.net_balance) || 0;
      netBalEl.textContent = `${net < 0 ? "-" : ""}$${Math.abs(net).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
      netBalEl.className = `kpi-value ${net >= 0 ? "income" : "expense"}`;
    }

    if (expEl) {
      const exp = Math.abs(Number(summary.total_expenditure) || 0);
      expEl.textContent = `$${exp.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }

    if (incEl) {
      const inc = Math.abs(Number(summary.total_income) || 0);
      incEl.textContent = `$${inc.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }

    if (idxBadge && summary.indices && summary.indices.length > 0) {
      const latest = summary.indices[summary.indices.length - 1];
      const val = latest.laspeyres_price_index || latest.jevons_index || 100.0;
      idxBadge.textContent = `${val.toFixed(2)}`;
    }
  }
}

customElements.define("peit-kpi-cards", PeitKpiCards);
