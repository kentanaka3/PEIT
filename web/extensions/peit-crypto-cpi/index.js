/**
 * Reference Extension: Crypto CPI Tracker
 * Evaluates expenditure in Bitcoin Satoshi denominations and tracks BTC/MXN FX pricing.
 */

class CryptoCpiView extends HTMLElement {
  connectedCallback() {
    this.render();
  }

  render() {
    this.innerHTML = `
      <div class="kpi-card" style="padding: 24px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <div>
            <h3 style="margin: 0; font-size: 16px; color: var(--md-sys-color-primary);">Crypto CPI & Real Satoshis Terminal</h3>
            <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--md-sys-color-outline);">
              Indexes personal expenditure against Bitcoin satoshi equivalence.
            </p>
          </div>
          <span style="background: rgba(247, 147, 26, 0.15); color: #f7931a; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; font-family: monospace;">
            BTC / MXN
          </span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px;">
          <div style="background: var(--md-sys-color-surface-container-high); padding: 16px; border-radius: 8px;">
            <div style="font-size: 11px; text-transform: uppercase; color: var(--md-sys-color-outline);">BTC Reference Price</div>
            <div id="crypto-btc-price" style="font-size: 20px; font-weight: 700; color: #f7931a; font-family: monospace; margin-top: 4px;">
              $1,185,000 MXN
            </div>
          </div>
          <div style="background: var(--md-sys-color-surface-container-high); padding: 16px; border-radius: 8px;">
            <div style="font-size: 11px; text-transform: uppercase; color: var(--md-sys-color-outline);">Total Spend (Sats)</div>
            <div id="crypto-total-sats" style="font-size: 20px; font-weight: 700; color: var(--md-sys-color-on-surface); font-family: monospace; margin-top: 4px;">
              Calculating...
            </div>
          </div>
          <div style="background: var(--md-sys-color-surface-container-high); padding: 16px; border-radius: 8px;">
            <div style="font-size: 11px; text-transform: uppercase; color: var(--md-sys-color-outline);">Purchasing Power Trend</div>
            <div id="crypto-cpi-trend" style="font-size: 20px; font-weight: 700; color: var(--peit-color-rate-badge); font-family: monospace; margin-top: 4px;">
              -4.2% (Deflationary)
            </div>
          </div>
        </div>

        <div style="border-top: 1px solid var(--md-sys-color-outline-variant); padding-top: 16px;">
          <h4 style="margin: 0 0 12px 0; font-size: 13px; text-transform: uppercase; color: var(--md-sys-color-outline);">
            Top Transactions Indexed in Satoshis
          </h4>
          <div id="crypto-tx-list" style="display: flex; flex-direction: column; gap: 8px; font-size: 12px; font-family: monospace;">
            <!-- Populated dynamically -->
          </div>
        </div>
      </div>
    `;
  }

  updateMetrics(entries) {
    const totalSatsEl = this.querySelector("#crypto-total-sats");
    const txListEl = this.querySelector("#crypto-tx-list");
    if (!totalSatsEl || !txListEl) return;

    const btcPriceMxn = 1185000;
    let totalSpend = 0;
    entries.forEach((e) => {
      const amt = Number(e.total_price) || 0;
      totalSpend += amt;
    });

    const totalSats = Math.round((totalSpend / btcPriceMxn) * 100000000);
    totalSatsEl.textContent = `${totalSats.toLocaleString()} sats`;

    const sampleTxs = entries.slice(0, 5);
    if (sampleTxs.length === 0) {
      txListEl.innerHTML = `<div style="color: var(--md-sys-color-outline);">No transaction entries loaded.</div>`;
      return;
    }

    txListEl.innerHTML = sampleTxs
      .map((tx) => {
        const amt = Number(tx.total_price) || 0;
        const sats = Math.round((amt / btcPriceMxn) * 100000000);
        return `
          <div style="display: flex; justify-content: space-between; padding: 6px 10px; background: var(--md-sys-color-surface-container); border-radius: 4px;">
            <span>${tx.merchant || "Unknown"} - ${tx.item || "Item"}</span>
            <span style="color: #f7931a; font-weight: bold;">${sats.toLocaleString()} sats ($${amt.toFixed(2)})</span>
          </div>
        `;
      })
      .join("");
  }
}

let unsubscribe = null;

export async function activate(context) {
  // 1. Register custom view component
  context.ui.registerView("crypto-cpi-view", CryptoCpiView);

  // 2. Set initial status bar item
  context.ui.updateStatusBarItem("btc-mxn-indicator", "BTC/MXN: 1,185,000", "Live Synthetic BTC/MXN FX Indicator");

  // 3. Listen to ledger entries changes
  const update = () => {
    const entries = context.ledger.getEntries();
    const views = document.querySelectorAll("crypto-cpi-view");
    views.forEach((v) => v.updateMetrics(entries));
  };

  unsubscribe = context.ledger.subscribeEntries((entries) => {
    const views = document.querySelectorAll("crypto-cpi-view");
    views.forEach((v) => v.updateMetrics(entries));
  });

  // Also listen for custom events if needed
  context.events.on("ledger:refreshed", update);

  // Initial update
  setTimeout(update, 100);
}

export async function deactivate() {
  if (unsubscribe) {
    unsubscribe();
    unsubscribe = null;
  }
}

