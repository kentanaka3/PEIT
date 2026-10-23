# PEIT prototype showcase — production storyboard

## Primary recording path: native Android

The Kotlin application in [`app/`](app/) is now the primary showcase.
The Python/web and Flutter storyboard below is retained as a separate,
optional walkthrough; do not splice the clients together as though their
ledgers synchronize. Android sync/outbox is deferred.

| Time | Android interaction | Required boundary |
|---|---|---|
| 0:00-0:30 | Introduce PEIT and show the local synthetic history. | Local-first prototype; synthetic data, not household observations. |
| 0:30-1:10 | Switch between Stream and Grid; inspect a record. | Two views of the same device database. |
| 1:10-2:30 | Capture/select a synthetic receipt, review fields and provisional analyst labels, balance and save; repeat with a second receipt. | Show only rehearsed behavior. Do not hide discrepancies or failed recognition. |
| 2:30-3:10 | Inspect ledger identity/hash-chain consistency. | SHA-256 identity hashes are not digital signatures or full-record authentication. |
| 3:10-4:15 | Show the equal-weight matched-item price indicator, coverage, and separate expenditure change. | Base = 100; single currency; insufficient history is not zero change; not official CPI. |
| 4:15-4:50 | Close with implemented scope and outstanding device/evaluation work. | No Android pairing, outbox, live web sync, or demonstrated social impact. |

Follow the [Android rehearsal checklist](README.md#rehearsal-and-acceptance-checklist)
before filming. If a step has not been verified on the recording device,
omit it or explicitly show the actual blocked state.

## Optional Python/web and Flutter storyboard

**Format:** moderated, task-based prototype walkthrough for a formal user-interaction evaluation
**Runtime:** 4:50 total, including opening and close
**Audience:** evaluation participants, reviewers, and people assessing the prototype's current scope
**Editorial rule:** show what a participant can actually do today; label derived outputs and limitations. This is a prototype demonstration, not evidence of usability, scientific validity, or social impact.

## Production brief

The film should let a viewer understand the user need, try to follow a realistic task, see how a result is derived, and distinguish working prototype functions from unfinished or illustrative elements. Keep the participant's interaction authentic: use a clean, isolated ledger populated only with deterministic synthetic rows, and do not stage successful behavior that was not observed in the recording.

### Pre-shoot checklist

- Use the web workbench with an **isolated** ledger, started by the operator with `./peit --ledger <isolated-ledger.jsonl> --serve --host 127.0.0.1 --port 8000 --no-broadcast`. Do not use a personal or production ledger.
- If sample rows are needed, an operator may generate deterministic synthetic data using `python3 -m peit.profiler generate --profile config/profiles/alice.json --market config/markets/mexico_2024.json --seed 42 --output <scratch-dir>/receipts.csv --manifest <scratch-dir>/ground_truth.json`, then import that CSV. Keep generated files and the ledger outside the tracked project data. Do not imply that the generated rows are real observations.
- The participant should receive a short task card, not a click-by-click script: “Using the provided sample data, find where you can review records, inspect the monthly price result and its coverage, and tell us what you think it does and does not mean.” Allow the participant to decide where to click. The moderator may repeat the prompt but should not coach unless the participant is blocked.
- Obtain informed recording consent before filming a participant. Use a pseudonym or no name in the edit; capture no personal receipt, account, financial, or identifying information. The repository's receipt images are real: do not open, inspect, copy, or show them. Public use of any real receipt requires permission and redaction.
- Rehearse the exact screens and controls on the recording machine. Use the built-in browser zoom/display settings as needed; avoid implying that the optional Flutter web island is available unless its compiled assets have been built and the island has been rehearsed.
- The film is a walkthrough, not an evaluation finding. Do not add participant quotations, success rates, performance claims, or impact claims unless separately collected, consented, analyzed, and approved.

### Capture and edit conventions

- Record a clean screen capture at 1080p or higher and a separate, close-miked voice track. Keep the cursor visible, large enough to follow, and move deliberately; pause briefly after each click so the viewer can register the state change.
- Frame the application at a readable scale. Hide desktop notifications, unrelated tabs, personal account names, local file paths, and any unneeded browser chrome. Use discreet editorial labels rather than altering application output.
- Use straight cuts or short dissolves between distinct topics; use a brief cursor-led cut or match cut when following an interaction. Do not add fake loading states, fabricated data, simulated OCR output, or unobserved participant reactions.
- Record narration after the participant session where possible. Keep the spoken track calm and explanatory, with no music under key instructions or caveats.

## Timed storyboard and narration

| Time | Picture, screen composition, and interaction | On-screen text | Spoken narration |
|---|---|---|---|
| **00:00–00:20** (20 s) | Open on a clean title over a neutral background, then cut to the web workbench at its home/overview state. Slow push-in only in the edit. Keep the participant and moderator off camera unless both have consented. No click yet. | **PEIT — Personal Expenditure & Inflation Tracker**  \| **Prototype walkthrough · task-based evaluation** | “A receipt says what was paid. PEIT explores how a person might review recorded purchases over time—and distinguish changing prices from changing spending. This is a prototype walkthrough, not an official inflation measure.” |
| **00:20–01:00** (40 s) | Show the task card briefly, then capture the participant reading it. Return to the workbench. The participant begins without coaching; follow their cursor at a readable pace. If the participant chooses the review table first, stay with that path. If not, let them explore naturally rather than forcing a route. | **Task:** Find records, inspect the monthly price result and coverage, explain what it means.  \| Small persistent corner label: **Synthetic sample data** | “For this evaluation task, the participant is asked to find the records, inspect a monthly price result and its coverage, and explain the limits in their own words. We use an isolated ledger with deterministic synthetic rows—not a personal receipt history. We observe the interaction; this short video does not report a study result.” |
| **01:00–01:40** (40 s) | Begin with a simple editorial diagram over a neutral background: **Browser → locally served web workbench → isolated ledger**; beside it, show **Mobile app → local SQLite**. Label the paths “separate prototype workflows,” then dissolve to the web workbench's review/data-grid area. Let the participant scan columns and select or scroll naturally. If import is part of the actual task, show the synthetic CSV selection and resulting review state; otherwise show the already-imported synthetic ledger. | **Web: local service + isolated ledger**  \| **Mobile: local SQLite**  \| **Separate local workflows · no cloud pairing implied** | “In this recording, the web workbench is served locally and uses an isolated ledger. The mobile prototype stores data in local SQLite. These are separate prototype workflows; this is not a cloud connection or live pairing. In the web view, the participant can review imported records before interpreting derived results. The rows shown are synthetic.” |
| **01:40–02:25** (45 s) | Move to the monthly index/dashboard view. Hold on the base month and later month if both are visible; point to the price result, matched-item coverage, and expenditure result in turn. Do not invent numerical examples: use only values actually displayed by the captured synthetic run. If coverage is absent or the data do not support a comparison, show the actual state and say so. | **Derived price index · base = 100**  \| **Equal-weight average of price relatives for matched item keys**  \| **Coverage matters** | “The price result is derived from matched item keys: each matched item's price relative is given equal weight, and the index is expressed relative to a base of 100. Coverage tells us how much of the base set matched. This is a personal-data-derived measure; it is not an official CPI, and a narrow match set should not be mistaken for a complete picture.” |
| **02:25–03:00** (35 s) | Keep the dashboard in view and move the pointer to the separate expenditure result. Use a split-screen overlay only if it preserves legibility; otherwise stay full-screen. Avoid presenting the two series as interchangeable or as a causal decomposition. | **Price change ≠ expenditure change**  \| **Expenditure also reflects quantities and purchase mix** | “The expenditure result answers a different question. Spending can change because prices changed, because quantities or purchase mix changed, or because of both. It is not a substitute for the price index, and the price index alone does not explain a household's full financial situation.” |
| **03:00–03:40** (40 s) | Cut to the mobile client. Show the card-stream review, then a short, deliberate transition to the data-grid review and local dashboard. Keep the device and screen recording synchronized. Do not show any personal ledger. Add no sync animation. | **Mobile prototype**  \| **Local SQLite storage**  \| **Card stream · data grid · local dashboard** | “The mobile prototype stores its data locally in SQLite and offers card-stream and data-grid review, alongside a local dashboard. This is a separate view of local data; do not read this scene as proof of cloud synchronization or live pairing with the web workbench.” |
| **03:40–04:20** (40 s) | Show the Home Scan/OCR control. Demonstrate its actual current interaction by pasting a short, purpose-made synthetic text snippet, then show the parser's response if it succeeds in the rehearsed build. Label the snippet as synthetic. Do not point a camera at a repository image. If this route fails during the take, stop and use the fallback guidance below rather than substituting an image-OCR result. | **Current Scan/OCR button: pasted text → parser**  \| **Image OCR service exists; not wired to this button**  \| **Benchmark: annotated text blocks, not live image-to-text evaluation** | “The current Home Scan/OCR button accepts pasted text and calls the text parser. An on-device ML Kit image-OCR service exists in the mobile code, but it is not wired to this button. The Python OCR benchmark uses annotated text blocks; it is not a live evaluation of converting receipt images into text. We keep those capabilities distinct.” |
| **04:20–04:50** (30 s) | Return to a composed end card, with a final glimpse of the workbench and mobile client side by side only if both were captured cleanly. Use a gentle fade. No graph animation implying future data or scaling results. | **Prototype stage**  \| **Potential uses are hypotheses, not demonstrated impact**  \| **Next: evaluate, improve, validate, test scalability** | “PEIT is at the prototype stage. Potential applications—such as helping people review their own recorded spending or supporting research prototypes—remain possibilities, not demonstrated social or scientific impact. Future work could expand supported inputs and evaluate reliability and scale; none is established today. Thank you.” |

**Total runtime: 4:50.** Keep the timing intact by trimming pauses between shots, not by rushing the participant's task or removing the methodological caveats.

## Visual and scientific accuracy notes

- The core price index is a **derived** result using an equal-weight average of price relatives for matched item keys, with a base of 100. The comparison is only as informative as the matched observations and their coverage. Never label it “official CPI,” “the cost of living,” or a validated inflation measure.
- Optional legible formula card: `I_t = 100 × mean(p_it / p_i0)` over matched item keys, where `0` denotes the base period. Keep the coverage caveat visible with the formula.
- Keep expenditure change separate from price change: expenditure reflects prices and quantities/purchase mix. Do not imply that the displayed measures establish why spending changed.
- The web workbench is served by the local command shown above. Do not portray it as a hosted service, cloud account, or live multi-device connection.
- Mobile data is stored locally in SQLite. Optional LAN sync, if separately rehearsed and included, must be called **local network sync**. Never imply cloud sync or live pairing unless that exact flow was rehearsed and verified for the recording.
- The mobile Scan/OCR button currently parses pasted text. ML Kit image OCR exists as a service in `mobile/lib/ocr/mlkit_service.dart` but is not connected to that button. Do not show an image being scanned as if this were the working button flow.
- Python OCR benchmarking uses annotated text blocks; it does not measure live image-to-text recognition from receipts.
- Crypto/BTC and carbon extension outputs are illustrative, hard-coded demo factors, not live or validated measurements. Omit them from the main story. If a reviewer requires them, show only a brief, clearly labeled “illustrative demo output—not live or validated” insert, and do not describe it as an estimate or impact.
- The Flutter web island depends on compiled assets and is optional. Include it only if those assets are available in the exact build being recorded; otherwise omit it without implying a missing user action.
- Any references to benefits, financial well-being, environmental effects, or wider social impact must be framed as **possible future applications or hypotheses**. Do not state a measured outcome.

## Accessibility, captions, and sound

- Provide accurate, human-reviewed captions for all narration and meaningful participant speech. Use speaker labels when needed; identify non-speech audio only when it conveys meaning. Do not auto-caption synthetic labels as if they were participant statements.
- Keep captions to no more than two lines at a time, with high contrast, a solid or semi-opaque backing, and placement that does not cover data, controls, or the participant's cursor. Proofread names, numbers, “base = 100,” “matched item keys,” and the OCR caveat against the final audio.
- Narrate the important visible action and distinguish interface labels from interpretation. Do not rely on color alone for status or coverage; read out the meaning when it is material.
- Keep interface text large enough to read at 1080p and avoid rapid zooms, flashing highlights, or fast cursor movements. Use brief holds on charts and data states.
- Mix speech clearly above any room tone. Prefer no music; if used, keep it low, instrumental, and ducked under speech and task instructions. Do not use sound effects that imply successful processing or synchronization.
- Supply a transcript alongside the video when publishing. Keep the persistent “synthetic sample data” and “prototype” labels legible in the final encode.

## Fallback and retake guidance

1. **Participant path differs from the storyboard:** Keep the real path. Reorder narration in voice-over or use a later clean screen capture to cover a topic; do not direct the participant to pretend they clicked something.
2. **Participant pauses, asks for help, or cannot find a view:** Leave the interaction intact for the evaluation record. The moderator may repeat the task prompt once. For a public showcase edit, include the genuine pause if useful, or cut to a separately recorded, clearly labeled operator walkthrough. Do not hide a usability difficulty while calling the video an evaluation.
3. **Web service or page does not load:** Do not fabricate a connected session. Retake with the isolated-ledger command and localhost setup checked by the operator before the participant arrives. If the service remains unavailable, replace the scene with a static diagram labeled “architecture overview,” and describe the intended local workflow—not a live demo.
4. **No valid match/coverage or an unexpected index state:** Show the observed result, explain that the data do not support the intended comparison, and retake only with a new deterministic synthetic dataset prepared through the approved demo setup. Never type in a convenient value or imply that unmatched data produced a valid index.
5. **Pasted-text parser fails:** Capture the failure honestly if it is part of the task. If a retake is needed, use a short, purpose-made synthetic text snippet and verify the parser response before filming. Do not switch to a real receipt image or imply that the button performs image OCR.
6. **Mobile view, local data, or optional island is unavailable:** Omit that scene or use a clearly labeled still from the same prototype build. Do not add a cloud-sync animation, pair devices in editing, or present a planned island as a working feature.
7. **Privacy or consent issue:** Stop recording. Delete or quarantine the affected footage under the team's approved process and reshoot with synthetic data and renewed consent. Never salvage identifying receipt details by cropping alone if they remain readable elsewhere in the frame.
8. **Audio, cursor, or caption defect:** Record clean narration separately, use a restrained cursor highlight in post, and regenerate/review captions against the final mix. Retake any screen segment where the visible state contradicts the narration.

## Repository references for producer fact-checking

- [Core calculations](../src/peit/core.py)
- [Mobile OCR service](../mobile/lib/ocr/mlkit_service.dart)
- [Mobile client guide](../doc/subsystems/mobile.md)
- [OCR subsystem notes](../doc/subsystems/ocr.md)
- [Profiler and synthetic data guide](../doc/subsystems/profiler.md)
- [Documentation map](../doc/README.md)