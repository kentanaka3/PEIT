/**
 * Reference Extension: ESG & Carbon Footprint Estimator
 * Computes estimated carbon impact per transaction category from context.ledger.getEntries().
 */

// Approximate emission factors in kg CO2e per currency unit (MXN)
const CATEGORY_EMISSION_FACTORS = {
  groceries: 0.12,
  transport: 0.35,
  utilities: 0.40,
  dining: 0.18,
  entertainment: 0.08,
  electronics: 0.25,
  clothing: 0.22,
  services: 0.05,
  default: 0.15,
};

class CarbonFootprintView extends HTMLElement {
  connectedCallback() {
    this.render();
  }

  render() {
    this.innerHTML = `
      <div class="kpi-card" style="padding: 24px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <div>
            <h3 style="margin: 0; font-size: 16px; color: #22c55e;">ESG & Carbon Footprint Estimator</h3>
            <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--md-sys-color-outline);">
              Measures personal household environmental impact across spending categories.
            </p>
          </div>
          <span style="background: rgba(34, 197, 94, 0.15); color: #22c55e; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; font-family: monospace;">
            ISO 14064 Scope 3
          </span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px;">
          <div style="background: var(--md-sys-color-surface-container-high); padding: 16px; border-radius: 8px;">
            <div style="font-size: 11px; text-transform: uppercase; color: var(--md-sys-color-outline);">Total Estimated Emissions</div>
            <div id="eco-total-co2" style="font-size: 20px; font-weight: 700; color: #22c55e; font-family: monospace; margin-top: 4px;">
              Calculating...
            </div>
          </div>
          <div style="background: var(--md-sys-color-surface-container-high); padding: 16px; border-radius: 8px;">
            <div style="font-size: 11px; text-transform: uppercase; color: var(--md-sys-color-outline);">Tree Offsets Required</div>
            <div id="eco-tree-offset" style="font-size: 20px; font-weight: 700; color: var(--md-sys-color-on-surface); font-family: monospace; margin-top: 4px;">
              0 trees
            </div>
          </div>
          <div style="background: var(--md-sys-color-surface-container-high); padding: 16px; border-radius: 8px;">
            <div style="font-size: 11px; text-transform: uppercase; color: var(--md-sys-color-outline);">Carbon Intensity</div>
            <div id="eco-intensity" style="font-size: 20px; font-weight: 700; color: var(--md-sys-color-primary); font-family: monospace; margin-top: 4px;">
              0.15 kg CO2e/$
            </div>
          </div>
        </div>

        <div style="border-top: 1px solid var(--md-sys-color-outline-variant); padding-top: 16px;">
          <h4 style="margin: 0 0 12px 0; font-size: 13px; text-transform: uppercase; color: var(--md-sys-color-outline);">
            Category Emissions Breakdown
          </h4>
          <div id="eco-category-breakdown" style="display: flex; flex-direction: column; gap: 8px; font-size: 12px; font-family: monospace;">
            <!-- Populated dynamically -->
          </div>
        </div>
      </div>
    `;
  }

  updateMetrics(entries) {
    const totalCo2El = this.querySelector("#eco-total-co2");
    const treeOffsetEl = this.querySelector("#eco-tree-offset");
    const intensityEl = this.querySelector("#eco-intensity");
    const breakdownEl = this.querySelector("#eco-category-breakdown");
    if (!totalCo2El || !breakdownEl) return;

    let totalCo2Kg = 0;
    let totalSpend = 0;
    const catEmissions = {};

    entries.forEach((e) => {
      if (!isConsumptionExpense(e)) return;
      const amt = Math.abs(Number(e.paid_total) || 0);
      const cat = (e.category || "default").toLowerCase();
      const factor = CATEGORY_EMISSION_FACTORS[cat] ?? CATEGORY_EMISSION_FACTORS.default;
      const co2 = amt * factor;

      totalSpend += amt;
      totalCo2Kg += co2;
      catEmissions[cat] = (catEmissions[cat] || 0) + co2;
    });

    totalCo2El.textContent = `${totalCo2Kg.toFixed(1)} kg CO2e`;
    const treesNeeded = Math.ceil(totalCo2Kg / 22); // ~22 kg CO2 absorbed per tree/year
    if (treeOffsetEl) treeOffsetEl.textContent = `${treesNeeded} trees / yr`;
    if (intensityEl && totalSpend > 0) {
      intensityEl.textContent = `${(totalCo2Kg / totalSpend).toFixed(2)} kg CO2e/$`;
    }

    const sortedCats = Object.entries(catEmissions).sort((a, b) => b[1] - a[1]);
    if (sortedCats.length === 0) {
      breakdownEl.innerHTML = `<div style="color: var(--md-sys-color-outline);">No transaction categories available.</div>`;
      return;
    }

    breakdownEl.innerHTML = sortedCats
      .map(([cat, co2]) => {
        const pct = totalCo2Kg > 0 ? ((co2 / totalCo2Kg) * 100).toFixed(0) : 0;
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: var(--md-sys-color-surface-container); border-radius: 4px;">
            <span style="text-transform: capitalize;">${cat}</span>
            <span style="color: #22c55e; font-weight: bold;">${co2.toFixed(1)} kg (${pct}%)</span>
          </div>
        `;
      })
      .join("");
  }
}

let unsubscribe = null;

export async function activate(context) {
  // 1. Register custom element view
  context.ui.registerView("carbon-footprint-view", CarbonFootprintView);

  // 2. Status bar updater helper
  const updateFootprint = () => {
    const entries = context.ledger.getEntries();
    let totalCo2Kg = 0;
    entries.forEach((e) => {
      const amt = Number(e.total_price) || 0;
      const cat = (e.category || "default").toLowerCase();
      const factor = CATEGORY_EMISSION_FACTORS[cat] ?? CATEGORY_EMISSION_FACTORS.default;
      totalCo2Kg += amt * factor;
    });

    const statusText = `ESG: ${totalCo2Kg.toFixed(1)} kg CO2e`;
    context.ui.updateStatusBarItem(
      "carbon-footprint-stat",
      statusText,
      `Estimated aggregate CO2e: ${totalCo2Kg.toFixed(1)} kg across ${entries.length} items`
    );

    const views = document.querySelectorAll("carbon-footprint-view");
    views.forEach((v) => v.updateMetrics(entries));
  };

  // 3. Subscribe to ledger changes
  unsubscribe = context.ledger.subscribeEntries((entries) => {
    updateFootprint();
  });

  // Initial update
  setTimeout(updateFootprint, 100);
}

export async function deactivate() {
  if (unsubscribe) {
    unsubscribe();
    unsubscribe = null;
  }
}

