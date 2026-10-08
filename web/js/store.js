// Graceful demonstration fallback data shown when daemon is offline
export const FALLBACK_SUMMARY = {
  status: "ok",
  balance: {
    total_income: 12500.0,
    total_expenditure: 397.0,
    net_transfers: 0.0,
    net_refunds: 0.0,
    net_balance: 12103.0,
  },
  category_breakdown: {
    groceries: 117.0,
    electronics: 280.0,
  },
  indices: [
    {
      month: "2026-08",
      fixed_basket_index: 100.0,
      changing_basket_expenditure_index: 100.0,
      coverage_percent: 100.0,
      expenditure: 397.0,
      status: "derived",
    },
    {
      month: "2026-09",
      fixed_basket_index: 102.15,
      changing_basket_expenditure_index: 100.0,
      coverage_percent: 100.0,
      expenditure: 397.0,
      status: "derived",
    },
  ],
  total_income: 12500.0,
  total_expenditure: 397.0,
  net_balance: 12103.0,
};

export const FALLBACK_ENTRIES = [
  {
    receipt_id: "RCP-2026-001",
    receipt_date: "2026-09-15",
    merchant: "Supermercado Central",
    item: "Organic Whole Milk 1L",
    brand: "Lala",
    category: "groceries",
    quantity: 2,
    pack_size: 1.0,
    unit: "l",
    unit_price: 28.5,
    currency: "MXN",
    discount: 0.0,
    fee: 0.0,
    tax: -4.56,
    deposit: 0.0,
    paid_total: -57.0,
    event_type: "one_off",
    store_tier: "A",
    store_rating: 4.5,
    brand_tier: "A",
    brand_rating: 4.8,
    product_tier: "A",
    product_rating: 4.7,
    availability: "in_stock",
    notes: "Weekly groceries batch (Demo Fallback)",
  },
  {
    receipt_id: "RCP-2026-002",
    receipt_date: "2026-09-16",
    merchant: "Panadería La Espiga",
    item: "Artisan Sourdough Loaf",
    brand: "In-House",
    category: "groceries",
    quantity: 1,
    pack_size: 500.0,
    unit: "g",
    unit_price: 65.0,
    currency: "MXN",
    discount: 5.0,
    fee: 0.0,
    tax: 0.0,
    deposit: 0.0,
    paid_total: -60.0,
    event_type: "recurring",
    store_tier: "B",
    store_rating: 4.8,
    brand_tier: "A",
    brand_rating: 5.0,
    product_tier: "A",
    product_rating: 4.9,
    availability: "in_stock",
    notes: "Fresh bakery item",
  },
  {
    receipt_id: "RCP-2026-003",
    receipt_date: "2026-09-20",
    merchant: "Tech Hub Electronics",
    item: "USB-C High Speed Cable 2m",
    brand: "Anker",
    category: "electronics",
    quantity: 1,
    pack_size: 1.0,
    unit: "pcs",
    unit_price: 280.0,
    currency: "MXN",
    discount: 0.0,
    fee: 0.0,
    tax: -44.8,
    deposit: 0.0,
    paid_total: -280.0,
    event_type: "one_off",
    store_tier: "A",
    store_rating: 4.6,
    brand_tier: "A",
    brand_rating: 4.9,
    product_tier: "A",
    product_rating: 4.8,
    availability: "in_stock",
    notes: "Office supplies",
  },
  {
    receipt_id: "RCP-2026-004",
    receipt_date: "2026-09-28",
    merchant: "Employer Direct Deposit",
    item: "Consulting & Engineering Retainer",
    brand: "Client",
    category: "income",
    quantity: 1,
    pack_size: 1.0,
    unit: "month",
    unit_price: 12500.0,
    currency: "MXN",
    discount: 0.0,
    fee: 0.0,
    tax: 0.0,
    deposit: 0.0,
    paid_total: 12500.0,
    event_type: "income",
    store_tier: "A",
    store_rating: 5.0,
    brand_tier: "A",
    brand_rating: 5.0,
    product_tier: "A",
    product_rating: 5.0,
    availability: "in_stock",
    notes: "Monthly fee payment",
  },
];

export class PeitStore extends EventTarget {
  constructor() {
    super();
    this.state = {
      transport: "checking", // "checking" | "online" | "offline" | "degraded"
      dataSource: "unavailable", // "unavailable" | "live" | "cached" | "demo"
      freshness: "unknown", // "unknown" | "current" | "stale"
      lastSuccessfulRefresh: null,
      error: null,
      summary: null,
      entries: [],
      filteredEntries: [],
      searchQuery: "",
      sortColumn: "receipt_date",
      sortAsc: false,
      selectedTab: "dashboard",
      theme: localStorage.getItem("peit-theme") || "dark",
      online: false,
      isFallback: false,
      lastUpdated: null,
      error: null,
    };
  }

  getState() {
    return this.state;
  }

  setState(partial) {
    this.state = { ...this.state, ...partial };
    this.dispatchEvent(new CustomEvent("statechange", { detail: this.state }));
  }

  async init() {
    await this.fetchHealth();
    await this.fetchSummary();
    await this.fetchEntries();

    // Start background health poll every 10s
    setInterval(() => this.fetchHealth(), 10000);
  }

  async fetchHealth() {
    try {
      const res = await fetch("/api/v1/health");
      if (res.ok) {
        const data = await res.json();
        this.setState({ health: data, online: true, error: null, isFallback: false });
      } else {
        this.handleOfflineState(`HTTP ${res.status} from health endpoint`);
      }
    } catch (err) {
      this.handleOfflineState(err.message);
    }
  }

  handleOfflineState(reason) {
    const wasFallback = this.state.isFallback;
    const updates = { online: false, error: reason };

    // If we have no summary or entries, supply graceful fallback data so UI never appears empty
    if (!this.state.summary || this.state.entries.length === 0) {
      updates.isFallback = true;
      if (!this.state.summary) {
        updates.summary = FALLBACK_SUMMARY;
      }
      if (this.state.entries.length === 0) {
        this.state.entries = FALLBACK_ENTRIES;
        this.applyFilterAndSort();
      }
    }

    this.setState(updates);
  }

  async fetchSummary(month = null, account = null) {
    try {
      const url = new URL("/api/v1/summary", window.location.origin);
      if (month) url.searchParams.set("month", month);
      if (account) url.searchParams.set("account", account);

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        this.setState({ summary: data, lastUpdated: new Date() });
      } else if (!this.state.summary) {
        this.setState({ summary: FALLBACK_SUMMARY, isFallback: true });
      }
    } catch (err) {
      console.warn("Summary fetch offline, using fallback data:", err.message);
      if (!this.state.summary) {
        this.setState({ summary: FALLBACK_SUMMARY, isFallback: true });
      }
    }
  }

  async fetchEntries(filters = {}) {
    try {
      const url = new URL("/api/v1/entries", window.location.origin);
      for (const [k, v] of Object.entries(filters)) {
        if (v !== null && v !== undefined) {
          url.searchParams.set(k, v);
        }
      }

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        this.state.entries = data;
        this.setState({ isFallback: false });
        this.applyFilterAndSort();
      } else if (this.state.entries.length === 0) {
        this.state.entries = FALLBACK_ENTRIES;
        this.setState({ isFallback: true });
        this.applyFilterAndSort();
      }
    } catch (err) {
      console.warn("Entries fetch offline, using fallback data:", err.message);
      if (this.state.entries.length === 0) {
        this.state.entries = FALLBACK_ENTRIES;
        this.setState({ isFallback: true });
        this.applyFilterAndSort();
      }
    }
  }

  setSearchQuery(q) {
    const cleaned = (q || "").toLowerCase();
    this.state.searchQuery = cleaned;

    if (this._searchDebounceTimer) {
      clearTimeout(this._searchDebounceTimer);
    }

    this._searchDebounceTimer = setTimeout(() => {
      this._searchDebounceTimer = null;
      this.applyFilterAndSort();
    }, 120);
  }

  setSorting(col) {
    if (this.state.sortColumn === col) {
      this.state.sortAsc = !this.state.sortAsc;
    } else {
      this.state.sortColumn = col;
      this.state.sortAsc = true;
    }
    this.applyFilterAndSort();
  }

  applyFilterAndSort() {
    const q = this.state.searchQuery;
    let list = this.state.entries || [];

    if (q) {
      list = list.filter((item) => {
        return (
          (item.item && item.item.toLowerCase().includes(q)) ||
          (item.merchant && item.merchant.toLowerCase().includes(q)) ||
          (item.category && item.category.toLowerCase().includes(q)) ||
          (item.receipt_id && item.receipt_id.toLowerCase().includes(q)) ||
          (item.brand && item.brand.toLowerCase().includes(q))
        );
      });
    }

    const col = this.state.sortColumn;
    const asc = this.state.sortAsc;

    list = [...list].sort((a, b) => {
      let va = a[col];
      let vb = b[col];

      if (va === null || va === undefined) va = "";
      if (vb === null || vb === undefined) vb = "";

      if (typeof va === "number" && typeof vb === "number") {
        return asc ? va - vb : vb - va;
      }

      const sa = String(va);
      const sb = String(vb);
      return asc ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });

    this.setState({ filteredEntries: list });
  }

  toggleTheme() {
    const nextTheme = this.state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("peit-theme", nextTheme);
    this.setState({ theme: nextTheme });
    document.documentElement.setAttribute("data-theme", nextTheme);
  }

  setActiveTab(tabId) {
    this.setState({ selectedTab: tabId });
  }
}

export const store = new PeitStore();
