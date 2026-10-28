# PEIT Showcase Demo

This guide prepares a repeatable PEIT demonstrator and a video of **no more
than five minutes**. The primary showcase is the native Kotlin Android
application in [`app/`](app/). The Python/web workbench and Flutter client
remain separate, optional workflows, documented below.

Use synthetic records only; do not expose anyone's personal receipts. The
Android application seeds an empty local database with synthetic history.
New receipt captures remain on that device. Android synchronization, pairing,
and an offline outbox are **not implemented**; do not imply that the Android,
Flutter, and Python ledgers share live data.

For the source-code map, see [`../MAP.md`](../MAP.md). For scientific scope
and project boundaries, see [`../AGENTS.md`](../AGENTS.md).

## Native Android showcase

### Responsive UI and visual design

The redesign targets readable receipt cards on phones and a data workspace
on genuinely wide content areas. Grid mode on a phone must scroll columns
horizontally rather than shrink headings into character fragments; its
inspector opens separately. Side-by-side inspection requires sufficient
available content width, not merely a tablet-sized device classification.
Enlarged system text must preserve readable controls and reachable actions.

Original SVG design concepts live in [`img/`](img/); launcher artwork lives
in the [Android resources](app/src/main/res/). These are interface design
artifacts, not evidence of usability or scientific validity. See
[the plan](.agent/plan.md#visual-redesign-2026-10-22) for implementation and
device-validation status.

| Visual concept | Purpose |
|---|---|
| [Phone receipt stream](img/01-phone-stream.svg) | Calm stacked cards, explicit local/synthetic provenance, separate price and expenditure concepts. |
| [Phone receipt review](img/02-phone-review.svg) | Full-width fields, visible uncertainty and a reachable reviewed-payment action. |
| [Tablet ledger workspace](img/03-tablet-ledger.svg) | Readable table columns and an evidence inspector only with sufficient workspace width. |
| [Identity and launcher mark](img/04-identity.svg) | Original receipt-and-signal logo, adaptive-icon geometry, ink/teal palette and small-size studies. |

Before a recording, verify both card and grid modes on the actual device.
Check the selection toolbar, header labels, inspector, navigation, and
verification payment/action area at default and enlarged font sizes.
Do not shrink fonts to disguise an undersized layout.

### Build prerequisites and offline checks

- An already installed Android SDK platform **37.2**, the project's cached
  Gradle/plugin dependencies, and its configured Java 25 toolchain.
- A device or emulator supporting **API 37 or newer**. The minimum SDK remains
  37; compiling against 37.2 does not broaden device compatibility.
- A local, ignored `local.properties` pointing at the installed SDK, or an
  `ANDROID_HOME` environment variable. Do not commit machine-specific paths.

From this directory, using an existing JDK on your machine:

```bash
export JAVA_HOME="/path/to/existing/jdk"
export PATH="$JAVA_HOME/bin:$PATH"
./gradlew --offline -Dorg.gradle.java.installations.auto-download=false \
  assembleDebug testDebugUnitTest lintDebug --console=plain
```

This command must not fetch dependencies or toolchains. If a prerequisite is
missing, stop and obtain approval before installing it. Passing unit tests
does not establish camera, PDF rendering, accessibility, or crash-free device
behavior. Run the existing instrumentation tests on a prepared API 37+
device separately:

```bash
./gradlew --offline -Dorg.gradle.java.installations.auto-download=false \
  connectedDebugAndroidTest --console=plain
```

### Rehearsal and acceptance checklist

1. Open the application and identify the seeded history as **synthetic**.
2. Show Stream and Grid as two views of the device's local records.
3. Capture or select a permission-approved synthetic receipt image, or choose
   a synthetic PDF. Review merchant, date, currency, items, and analyst labels.
   Unknown OCR fields must be corrected rather than silently invented.
4. Confirm that the observed payment balances. Save, then repeat with a second
   receipt in the same session. A discrepant receipt must not be committed.
5. Explain that expenses are negative. Receipt-level adjustments are allocated
   proportionally to item subtotals at cent precision, with a deterministic
   remainder correction; saved item totals must equal the reviewed payment.
6. Inspect ledger identity/hash-chain consistency. SHA-256 identifiers are
   **not digital signatures**, and this check does not authenticate every
   mutable label or promise tamper-proof storage.
7. Show the derived matched-item price indicator and its coverage, separately
   from expenditure change. Demonstrate insufficient history honestly.

Analyst tiers and ratings are not OCR observations or scientific results.
Provisional defaults must be visible and reviewed before saving.

### Index interpretation

Android follows the Python/Flutter matched-item methodology, rather than the
original Android plan's Laspeyres/Paasche/Fisher dashboard. For each item and
period, the average unit price is `sum(quantity * unit_price) / sum(quantity)`.
For matched item keys `M`, the price indicator is:

```text
price_index = 100 * mean(current_item_price / base_item_price for item in M)
coverage_percent = 100 * matched_item_count / base_item_count
expenditure_index = 100 * current_consumption_expenditure / base_consumption_expenditure
```

Use confirmed consumption records (`recurring` or `one_off`) and a single
currency; there is no exchange-rate conversion. Missing matches or unusable
history must not be presented as zero price change. Expenditure uses absolute
signed payments and reflects quantities and purchase mix as well as prices.
These are derived prototype indicators, not official CPI figures.

### Verification record

See [the implementation plan](.agent/plan.md) for current task and validation
status. On 2026-10-22, offline debug and instrumentation APK builds and all
**48 JVM unit tests** passed. Instrumentation tests were compiled, not run.
Lint remains blocked by uncached desktop/JVM Compose and DataStore
dependencies; no dependencies were downloaded and lint was not bypassed.
Device rehearsal remains required before recording; do not describe
unexecuted camera, rotation, tablet, or accessibility checks as passed.

The Room migration preserves legacy rows and identity hashes. Legacy hash
compatibility does not authenticate historical data or silently convert old
quality labels and event types into canonical observations. Review legacy
records before interpreting them; unsupported event types are excluded from
consumption indices.

## Separate Python/web and Flutter workflows

The remainder of this guide describes the existing Python/web plus Flutter
walkthrough. Its mobile limitations refer to the Flutter client, **not** the
native Android capture screen. These workflows do not demonstrate native
Android synchronization.

## Showcase in one sentence

**PEIT turns reviewed receipt-line observations into a locally computed view
of a person's spending and matched-item price changes, with an optional path
to inspect records in a desktop workbench.**

Describe the output as a *derived personal price indicator*, not as an
official CPI or a validated measure of every household's cost of living.
Keep recorded observations, user-assigned matching labels, derived indices,
and illustrative estimates distinct throughout the presentation.

## What the demonstrator shows

| Showcase requirement | What to demonstrate | Evidence and boundary |
|---|---|---|
| Problem or need | A national average basket can differ from an individual's observed purchases. | Present this as PEIT's motivating problem, not as a measured result from this demo. |
| Scientific and technological foundations | Receipt-line observations, normalized item keys, signed transactions, local calculations, and reproducible synthetic history. | The core index uses matched items and an equal-weight average of item price relatives; expenditure change also reflects quantities and basket composition. State the formula when interpreting results. |
| Architecture and methodology | Profile × market generation, receipt schema validation, mobile SQLite, Python JSONL ledger with SQLite projection, and local REST/web workbench. | Synthetic records are generated by the profiler; they are not real household observations. |
| Prototype functionality | Generate/import data, view KPIs and ledger rows in the workbench, and parse/review/save a sample receipt in the mobile app. | The mobile home screen's “Scan / OCR” action currently accepts pasted OCR text. The on-device ML Kit service exists, but the image-processing path is not wired to that screen. |
| Potential applications and impact | Household expenditure reflection, personal price monitoring, and research or education about how basket choice affects measured price change. | These are potential applications and hypotheses, not demonstrated social or economic impact. |
| Development stage | A local-first prototype with working Python data, ledger, API, browser workbench, Flutter client, and OCR components. | It is not a production financial service or a validated official inflation statistic. |
| Future work and scalability | Image capture-to-review integration, broader evaluation, accessibility testing, explicit index methodology, and robust multi-device synchronization. | Separate current implementation from proposed work. |

## Run the working web demonstrator

### Prerequisites

- Run these commands from the repository root.
- Use the configured PEIT Python environment. The repository instructions use
  Python 3.13 and set `PYTHONPATH` to `src/`.
- `curl` and a browser are useful for the health check and workbench.
- Flutter is optional for the web-only run; use a Flutter-enabled device or
  emulator for the mobile portion.

Activate an already configured environment; do not install packages during a
live evaluation.

```bash
conda activate "$PWD/.venv/PEIT"
export PATH="$CONDA_PREFIX/bin:$PATH"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
```

### Create an isolated, reproducible dataset

This generates synthetic receipt rows and a ground-truth manifest using the
repository's example consumer profile and market. All generated files stay
outside the repository.

```bash
DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/peit-showcase.XXXXXX")"
printf 'Demo data directory: %s\n' "$DEMO_DIR"

python3 -m peit.profiler generate \
  --profile config/profiles/alice.json \
  --market config/markets/mexico_2024.json \
  --seed 42 \
  --output "$DEMO_DIR/receipts.csv" \
  --manifest "$DEMO_DIR/ground_truth.json"

./peit \
  --ledger "$DEMO_DIR/ledger.jsonl" \
  --import "$DEMO_DIR/receipts.csv"

./peit \
  --ledger "$DEMO_DIR/ledger.jsonl" \
  --balance --account all --json
```

Keep the printed `DEMO_DIR` value available for the server command. Do not
substitute `data/ledger.jsonl`: the showcase should use its isolated ledger.

### Start the daemon and open the workbench

In the same terminal, start the daemon against that isolated ledger:

```bash
./peit \
  --ledger "$DEMO_DIR/ledger.jsonl" \
  --serve --host 127.0.0.1 --port 8000 --no-broadcast
```

Leave it running. In a browser, open `http://127.0.0.1:8000`. The web
workbench should show live daemon status, summary cards, and transaction
rows. Confirm the API is responding before recording:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
```

Use the activity bar to open **Ledger** and search for a generated merchant
or item. The workbench's **Crypto CPI** and **Carbon Footprint** extensions
are optional interface demonstrations. Their exchange rate and emission
factors are illustrative constants, not live feeds or validated estimates.

### Optional mobile walkthrough

In a separate terminal with Flutter installed:

```bash
cd mobile
flutter pub get
flutter run
```

On the mobile Home screen:

1. Tap **Scan / OCR** and paste the synthetic sample below.
2. Tap **Parse & Review**.
3. Review the parsed lines; approve or discard as appropriate.
4. Commit the reviewed rows to the device's local SQLite ledger.
5. Open the mobile dashboard to show local cash-flow/category summaries.

```text
OXXO
2026-10-15
LECHE LALA ENTERA 1L 25.00
PAN BIMBO BLANCO 500G 38.00
TOTAL 63.00
```

This current Home-screen flow demonstrates text parsing and human review; it
does not demonstrate image capture. PEIT also has an on-device ML Kit service
in [`../mobile/lib/ocr/mlkit_service.dart`](../mobile/lib/ocr/mlkit_service.dart)
that processes an image file, but the service is not currently invoked by the
Home screen's “Scan / OCR” action. To show live image recognition, use a
separately verified harness or first connect image selection/capture to the
service and rehearse that path. The Python real-photo benchmark uses annotated
text blocks for parser evaluation; it is not a live image-to-text OCR run.

The repository's [`../test/data/receipts/`](../test/data/receipts/) corpus
contains real receipts. Do not show or copy those images into a public demo
without owner permission and appropriate redaction. The default walkthrough
does not read or display them.

### Optional LAN synchronization

LAN pairing and sync are not required for the baseline five-minute
demonstration. If you include them, rehearse pairing on the actual device,
network, host address, and isolated ledger before evaluation. Use the same
ledger and device-registry paths for pairing and serving. Keep authentication
enabled; do not use `--insecure-lan` for a public or formal evaluation. If
pairing or sync is not verified, show the mobile local-first workflow and the
workbench as separate prototype surfaces rather than implying they share
live data.

## Five-minute video plan and narration

Record at 1080p if available, with readable text, captions, a visible cursor,
and no personal financial information. Keep the video under five minutes;
the following target timings total **4:50**.

| Time | Visual | Narration |
|---|---|---|
| **0:00–0:25** | Title: “A Receipt Becomes a Personal Price Signal.” Briefly show the mobile app and workbench. | “Official price measures summarize a population. PEIT explores how a person's own observed purchases can support a more personal view.” |
| **0:25–0:55** | Show the flow: receipt → review → local ledger → derived indicator → optional desktop view. | “The prototype combines a canonical receipt schema, on-device storage, a Python ledger/API, and a browser workbench. Observations and derived values remain separate.” |
| **0:55–1:45** | In the mobile Home screen, paste the sample text, parse it, review the item lines, then commit. | “Here the current user-facing capture path parses pasted OCR text. The person reviews the output before it is saved locally. ML Kit image recognition is also implemented as a service, but is not yet connected to this Home-screen action.” |
| **1:45–2:30** | Show the mobile dashboard and local category/cash-flow summaries. | “These summaries are computed from the device's local ledger. With one month, the price index is only at its base; a meaningful change comparison needs multiple periods and matched item keys.” |
| **2:30–3:25** | Switch to the live web workbench. Show daemon provenance, KPIs, open Ledger, and search a row. | “This view uses reproducible synthetic history from the example Profile × Market generator. The ledger grid exposes the receipt records behind the summary.” |
| **3:25–4:00** | Highlight index, matching/coverage, or the data-flow diagram. | “The core fixed-basket indicator starts at 100 and averages price relatives for matched items. It is not an official CPI; expenditure change also reflects quantities and basket composition.” |
| **4:00–4:25** | Show an extension briefly, or show the workbench offline banner as a provenance example. | “Extensions illustrate how new views can consume ledger entries. These current crypto and carbon outputs are explicitly illustrative.” |
| **4:25–4:50** | Closing slide: current stage and next steps. | “PEIT is a local-first prototype. Next steps include integrating image capture with review, evaluating usability and accessibility, validating methods and data provenance, and hardening multi-device sync.” |

If the mobile build is unavailable, keep the video honest: show the web
workbench live and use a prepared mobile recording or screenshots clearly
identified as captured from the prototype. Do not simulate a successful
pairing, camera OCR, or cross-device sync that was not actually run.

## Formal user-interaction evaluation

Use a short, consent-based session with synthetic records. Do not ask
participants to enter personal financial information or expose real receipt
images. Give a neutral task prompt, observe without coaching, and record
aggregated notes rather than unnecessary identifying details.

Suggested tasks:

1. Find and explain one receipt row in the web ledger.
2. Parse and review the synthetic receipt text on mobile, then save it.
3. Identify which displayed values are observations, derived indicators, or
   illustrative extension estimates.
4. Locate the data-source/status indicator and explain whether the workbench
   is live or showing fallback data.

For each task, note completion, time, errors/retries, and assistance required.
Afterward ask participants to rate perceived usefulness and ease of use (for
example, 1–5) and invite comments. Use the following checklist:

| Evaluation dimension | What to observe |
|---|---|
| Usability / UX | Can participants understand the flow and complete tasks without coaching? |
| Functionality | Do parse, review, local save, dashboard, and live workbench behave as shown? |
| Accessibility | Can participants navigate with keyboard/screen reader where supported? Are labels, contrast, focus, and text size usable? |
| Innovation | Do participants understand the local-first, individualized-observation approach? |
| Perceived usefulness | Which screen or derived view, if any, helps them reason about their own expenditure? |
| Technical robustness | Record latency, failed requests, malformed parses, offline behavior, and recovery. |
| Educational / scientific / social impact | Do participants understand the limits of a personal indicator and the distinction between price and expenditure change? Treat impact as perceived potential, not measured outcome. |

## Development stage and next work

**Current stage:** local-first prototype / proof of concept. The Python
schema, validation, index calculations, JSONL ledger and SQLite projection,
REST server, web workbench, Flutter local database, review screens, and
on-device ML Kit service are present. The five-minute baseline demonstrates
the working web and mobile paths without requiring LAN pairing.

**Known integration/evaluation boundaries:**

- The Home screen's “Scan / OCR” action accepts text; wire image capture or
  selection to the ML Kit service for an end-to-end image OCR interaction.
- The Python real-photo benchmark evaluates parser output from annotated OCR
  text blocks; do not report it as OCR engine accuracy.
- Use multiple months and repeated item keys before interpreting an index
  trend; show the formula and matched coverage.
- Pairing, TLS, embedded Flutter web mounting, and cross-device sync need
  rehearsal in the exact demonstration environment.
- Extension values are illustrative and should not be presented as validated
  carbon accounting or current cryptocurrency exchange data.

**Future work:** improve image-to-review UX and OCR evaluation; conduct
accessibility and usability studies; formalize and consistently label index
methodology; strengthen provenance and reproducibility; test sync across
supported devices and network conditions; and scale storage/query handling
only with measured workloads and privacy review.

## Implementation references

These source locations anchor the instructions above; line numbers refer to
the current repository version.

| Demonstrated behavior | Implementation |
|---|---|
| Synthetic profile/market CSV and manifest generation | [`src/peit/profiler/cli.py`](../src/peit/profiler/cli.py), lines 213–250 and 304–411; example inputs: [`config/profiles/alice.json`](../config/profiles/alice.json), [`config/markets/mexico_2024.json`](../config/markets/mexico_2024.json) |
| CSV validation and core monthly indices | [`src/peit/core.py`](../src/peit/core.py), lines 51–201 |
| Daemon CLI options and startup | [`src/peit/cli.py`](../src/peit/cli.py), lines 32–111 and 502–550; [`src/peit/server.py`](../src/peit/server.py), lines 932–1032 |
| Workbench health, summary, entries, and snapshot state | [`src/peit/server.py`](../src/peit/server.py), lines 90–132 and 262–353; [`web/js/store.js`](../web/js/store.js), lines 204–390 |
| Mobile image OCR service | [`mobile/lib/ocr/mlkit_service.dart`](../mobile/lib/ocr/mlkit_service.dart), lines 10–64 |
| Current mobile paste-text and review entry path | [`mobile/lib/screens/home_screen.dart`](../mobile/lib/screens/home_screen.dart), lines 270–328; [`mobile/lib/controllers/receipt_review_controller.dart`](../mobile/lib/controllers/receipt_review_controller.dart), lines 140–377 |
| Mobile local monthly index and dashboard | [`mobile/lib/services/econometric_engine.dart`](../mobile/lib/services/econometric_engine.dart), lines 70–210; [`mobile/lib/screens/dashboard_screen.dart`](../mobile/lib/screens/dashboard_screen.dart), lines 60–160 and 546–648 |

## Demo cleanup

Stop the daemon with `Ctrl+C`. Generated files are in the temporary directory
printed by the preparation step; retain them only as long as needed for the
demonstration, then remove that specific directory manually. Do not put
generated ledgers, manifests, or receipt images into the repository.