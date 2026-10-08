# RFC-003: PEIT Web UI/UX Integration Architecture Specification
## Hybrid Micro-Shell, VS Code-Style Extensions, Multi-User Portal, and Cloud Scalability

**Status:** Approved Architectural Blueprint  
**Version:** 1.0.0  
**Target Directory:** `web/`  
**Integration Point:** `src/peit/server.py` (`peit --serve`)  
**Design Language:** Material 3 Dark/Light Financial Terminal (Monospace numbers, dynamic tokens, high data density)

---

## 1. Executive Summary & Core Architectural Decisions

Following comprehensive technical investigations across frontend runtimes, cloud infrastructure, and distributed telemetry, this document establishes the production design for PEIT's **Web UI/UX Integration**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          PEIT WEB WORKBENCH (Micro-Shell)                              │
│         Vanilla Modern Web (HTML5 / ES Modules / Web Components / Material 3)          │
├────────────────────────────────┬───────────────────────────────┬───────────────────────┤
│    PRIMARY EXTENSION HOST      │       EMBEDDED ISLANDS        │   USAGE & TELEMETRY   │
│ • Activity Bar & Panel Router  │ • Card Stream (Flutter Web)   │ • Real-time Admin HUD │
│ • Multi-Grid Transaction Table │ • OCR Bounding Box Inspector  │ • Storage Quota Meter │
│ • Econometric Graph Explorer   │ • Reuses mobile/lib/screens   │ • Latency & IOPS Sync │
│ • VS Code-style Plugin Sandbox │   via flutter.js DOM Island   │ • Prometheus /metrics │
└────────────────────────────────┴───────────────────────────────┴───────────────────────┘
                                 │
                   HTTP REST + Server-Sent Events (SSE)
                                 │
┌────────────────────────────────▼───────────────────────────────────────────────────────┐
│                          PEIT DESKTOP DAEMON & BACKEND                                 │
│                           src/peit/server.py & core.py                                 │
│     • Self-Hosted Local/Family Tenant Manager  • Pluggable StorageBackend (POSIX / S3) │
│     • Deterministic SSOT JSONL + SQLite WAL    • OpenTelemetry Metrics Engine         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Pillars:
1. **Hybrid Architecture (Vanilla Shell + Flutter Element Embedding)**:
   The workbench shell, high-density data grids, econometric visualizers, and extension manager run in **Pure Vanilla Modern Web** (sub-50ms INP, instant LCP, zero build-step overhead). Specialized mobile screens from `mobile/lib` (Card Stream swipe view and OCR canvas cropper) are embedded on-demand inside targeted DOM containers (`<div id="flutter-island">`) via Flutter 3.x+ **Element Embedding (`flutter.js`)**.
2. **VS Code-Style Extension Architecture (`web/extensions/`)**:
   Third-party developers and users can customize or extend PEIT without modifying core source code. Extensions register custom panels, toolbars, formatters, and chart transformers through standard Web Components and declarative manifests.
3. **Multi-User Family Portal & Zero-Lockin Cloud Path**:
   Begins as a self-hosted family portal on home servers/NAS/Docker with strict tenant isolation (`data/tenants/{id}/ledgers/{id}/`). Transitions with zero rewrites to **GCP (Cloud Run + GCS)** and **AWS (ECS Fargate + S3)** via pluggable `StorageBackend` and `AuthProvider` interfaces.
4. **Usage Monitoring & Telemetry Engine**:
   Production-grade resource metering (CPU/memory, query latency, storage quota bytes, active sessions, and OCR throughput) with an embedded Admin HUD and Prometheus `/metrics` endpoint.

---

## 2. Hybrid Frontend Architecture: Vanilla Micro-Shell + Flutter Islands

```
                                  index.html (Vanilla Shell)
                                              │
         ┌────────────────────────────────────┼────────────────────────────────────┐
         ▼                                    ▼                                    ▼
┌───────────────────┐               ┌───────────────────┐                ┌───────────────────┐
│ Activity Bar & Nav│               │ High-Density Grid │                │ Flutter Island    │
│ (Material 3 Tabs) │               │ (Vanilla Web Comp)│                │ (<div id="island">│
│ • Dashboard       │               │ • 25 Columns      │                │ • flutter.js      │
│ • Transactions    │               │ • Virtual Scroll  │                │ • CardStreamScreen│
│ • Profiler Studio │               │ • Inline Editing  │                │ • SnippetCropper  │
│ • Extensions      │               │ • Batch Bulk Ops  │                │ • Lazy Wasm Load  │
└───────────────────┘               └───────────────────┘                └───────────────────┘
```

### 2.1 The Host Shell (`web/src/shell/`)
- **Technology**: Pure ES2024 Modules, standard CSS Custom Properties for Material 3 tokens, and native Web Components (`customElements.define`).
- **Core Bundle Size**: **~45 KB uncompressed**. Delivers instant First Contentful Paint (<200ms) and eliminates virtual DOM diffing overhead.
- **State Store**: Reactive EventTarget-based store (`PeitStore`) connecting to `src/peit/server.py` via REST and Server-Sent Events (SSE) for live sync updates.

### 2.2 Flutter Element Embedding (`web/src/islands/flutter_island.js`)
When the user switches to mobile review view:
1. `flutter_island.js` injects `flutter.js` lazily.
2. Initializes the Flutter engine targeting the specific host DOM container:
   ```javascript
   await _flutter.loader.load({
     onEntrypointLoaded: async (engineInitializer) => {
       const appRunner = await engineInitializer.initializeEngine({
         hostElement: document.querySelector('#flutter_receipt_island'),
         renderer: 'canvaskit',
       });
       await appRunner.runApp();
     }
   });
   ```
3. Communicates with the host shell via `dart:js_interop` (`window.peitHostBridge` and `window.dispatchEvent`).

---

## 3. VS Code-Style Extension Architecture (`web/extensions/`)

PEIT provides an extension framework mirroring the Visual Studio Code workbench model.

### 3.1 Extension Manifest (`extension.json`)
Every extension declares its capabilities, contributions, and configuration schema:

```json
{
  "id": "peit-crypto-cpi-tracker",
  "name": "Crypto & Currency Substitution Index",
  "version": "1.0.0",
  "author": "Community",
  "main": "dist/index.js",
  "contributes": {
    "views": [
      {
        "id": "crypto-cpi-view",
        "title": "Crypto CPI Gap",
        "location": "sidebar",
        "icon": "currency_bitcoin"
      }
    ],
    "commands": [
      {
        "id": "crypto.calculateGap",
        "title": "Calculate Crypto Purchasing Power"
      }
    ],
    "settings": {
      "crypto.baseAsset": {
        "type": "string",
        "default": "BTC",
        "description": "Base comparison asset for purchasing power index"
      }
    }
  }
}
```

### 3.2 Extension Lifecycle & Host API (`PeitExtensionHost`)
Extensions run inside sandboxed Web Workers or isolated iframes with restricted access to the `peit` global API:
- `peit.ledger.getEntries(query)`: Query sanitized transaction rows.
- `peit.ui.registerView(id, customElement)`: Mount custom Material 3 UI widgets into sidebar, main tabs, or bottom inspector panels.
- `peit.metrics.registerIndicator(calcFn)`: Inject custom price index calculations into the Econometric Explorer.

---

## 4. Multi-User Family Portal & Cloud Scalability

### 4.1 Tenant & Ledger Isolation Hierarchy
Each household or tenant maintains strictly isolated physical storage to protect line-level SHA-256 signatures:
```text
data/
└── tenants/
    └── household_fam01/
        ├── tenant.json                         # Household metadata, quota, and roles
        └── ledgers/
            ├── shared_grocery/
            │   ├── ledger.jsonl                # Authoritative append-only SSOT
            │   └── ledger.db                   # Self-healing SQLite projection
            └── personal_alice/
                ├── ledger.jsonl
                └── ledger.db
```

### 4.2 Pluggable Storage & Auth Contracts (`src/peit/storage/` & `src/peit/auth/`)
```python
class StorageBackend(Protocol):
    async def append_entries(self, ledger_ref: str, entries: list[LedgerEntry]) -> int: ...
    async def stream_entries(self, ledger_ref: str) -> AsyncIterator[LedgerEntry]: ...
    async def get_query_engine(self, ledger_ref: str) -> sqlite3.Connection | Any: ...
    async def get_storage_stats(self, tenant_id: str) -> StorageFootprint: ...
```
- **Local / Self-Hosted**: `PosixStorageBackend` (`Path.open`, POSIX `flock`, `sqlite3.connect`).
- **Cloud (GCP / AWS)**: `ObjectStorageBackend` (stores JSONL in GCS / S3 with object versioning, queries served via Cloud SQL / Aurora Serverless or Litestream replicas).

---

## 5. Usage Monitoring & Resource Telemetry Subsystem

### 5.1 Telemetry Catalog & Core Dimensions

| Dimension | Metric | Type | Labels | Alert Trigger / Limit |
|---|---|---|---|---|
| **Resource** | `peit_process_cpu_seconds`<br>`peit_process_memory_rss_bytes` | Counter<br>Gauge | `node_id`, `worker` | Process RSS > 512 MB |
| **Consumption** | `peit_user_transaction_writes_total`<br>`peit_user_api_requests_total` | Counter<br>Counter | `tenant_id`, `user_id`<br>`tenant_id`, `route` | Rate limit: 120 req/min, 30 pushes/min |
| **Latency** | `peit_http_request_duration_seconds`<br>`peit_sqlite_query_duration_seconds` | Histogram<br>Histogram | `route`, `status_code`<br>`operation`, `ledger_id` | p95 request duration > 100ms |
| **Storage Quota** | `peit_ledger_storage_bytes`<br>`peit_quota_utilization_ratio` | Gauge<br>Gauge | `tenant_id`, `ledger_id`<br>`tenant_id`, `quota_type` | Soft warning: >80%, Hard write block: 100% |
| **Sessions** | `peit_active_paired_devices`<br>`peit_active_sync_connections` | Gauge<br>Gauge | `tenant_id`, `platform`<br>`tenant_id`, `state` | Disconnected or revoked token cleanup |

### 5.2 Embedded Admin Status HUD (`web/src/components/admin_hud.js`)
An embedded status panel accessible at `/admin/hud` rendering SVG sparklines for live query latencies, per-ledger storage bars, paired device revocations, and system uptime.

---

## 6. Phased Implementation Roadmap

```text
Phase 1: Hybrid Foundation & Static Web Serving
  ├── Step 1.1: Web Asset Scaffolding (web/index.html, Material 3 Dark/Light CSS)
  ├── Step 1.2: Embedded Web Server (src/peit/server.py static file serving)
  └── Step 1.3: Responsive Multi-Grid Ledger & Econometric Explorer

Phase 2: Mobile Island Integration (flutter.js)
  ├── Step 2.1: Flutter Web Target & Island Entrypoint (mobile/lib/web_island.dart)
  └── Step 2.2: JavaScript-to-Dart Interop Bridge (CustomEvents & data passing)

Phase 3: VS Code-Style Extension Framework
  ├── Step 3.1: Extension Registry & Manifest Parser (web/src/extensions/)
  └── Step 3.2: Custom Panel & Formula Extension Sandbox

Phase 4: Multi-User Portal, Cloud Readiness & Telemetry
  ├── Step 4.1: Multi-Tenant Router & Pluggable Storage Protocol
  ├── Step 4.2: Usage Monitoring Telemetry Collector & /metrics Endpoint
  └── Step 4.3: Docker Compose Self-Hosted Stack & GCP/AWS Config Templates
```

