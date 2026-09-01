# Production-Ready Architecture Decision Record Template

Use this template for material architectural, security, data, platform, or
operational decisions. Copy it to the project ADR directory, replace every
placeholder, and preserve the completed record as an immutable historical
decision. Use ISO dates and repository-relative links. An ADR records a
decision; it does not authorize production access, deployment, or publication.

## Repository conventions

PEIT stores numbered ADRs in `doc/adr/` using the filename pattern
`NNNN-kebab-case-title.md`, where `NNNN` is a unique zero-padded identifier.
The companion `doc/adr/README.md` contains the generated index. Create and
maintain these files with:

```bash
bash LLM/scripts/handler.sh adr init
bash LLM/scripts/handler.sh adr new "Short imperative decision title"
bash LLM/scripts/handler.sh adr update
```

The title identifier, filename identifier, and index entry must agree. Titles
must be non-empty, readable in Markdown table cells, and safe for a filename;
avoid control characters and unescaped table delimiters such as `|`. Do not
edit a historical ADR to rewrite its decision. Record a replacement ADR and
use `Superseded by ADR-XXXX` when the earlier decision is no longer current.

## Required metadata

Every numbered ADR must contain exactly one occurrence of each metadata field
below near the top of the document:

| Field | Requirement |
|---|---|
| `Status` | One of `Proposed`, `Accepted`, `Deprecated`, `Rejected`, `Superseded`, or `Superseded by ADR-XXXX` |
| `Deciders` | Named people or accountable roles |
| `Consulted` | Consulted teams or `None` |
| `Informed` | Impacted teams or `None` |
| `Date` | A real calendar date in `YYYY-MM-DD` format |
| `Technical Story / Ticket` | Traceable issue, ticket, or `None` |
| `Review Date` | A real date or `Not scheduled` |
| `Supersedes` | An ADR identifier or `None` |
| `Superseded by` | An ADR identifier or `None` |

The title must match `# ADR-NNNN: Title`, and the file must contain the
numbered sections in this template, including the decision outcome, security
and privacy assessment, consequences, implementation/validation plan, and
references/evidence. Replace placeholders before changing status to
`Accepted`; an unresolved placeholder is not evidence of completion.

The handler's current lightweight lint checks status and date syntax. CI also
checks the generated index. Required-field, section, placeholder, title/file
consistency, and calendar-date validation remain review responsibilities until
the validator explicitly implements them.

```markdown
# ADR-[NUMBER]: [Short, Imperative Title Summarizing the Decision]

* **Status:** [Proposed | Accepted | Superseded by ADR-XXXX | Deprecated | Rejected]
* **Deciders:** [Name/Role of Lead Architect, Tech Lead, SRE, etc.]
* **Consulted:** [Domain Experts, Security, Infrastructure Teams]
* **Informed:** [Impacted Engineering Teams]
* **Date:** [YYYY-MM-DD]
* **Technical Story / Ticket:** [JIRA-XXXX / GitHub Issue #]
* **Review Date:** [YYYY-MM-DD or Not scheduled]
* **Supersedes:** [ADR-XXXX or None]
* **Superseded by:** [ADR-XXXX or None]

---

## 1. Context and Problem Statement

[Describe the technical context, business constraints, system boundaries, and
operational triggers that necessitate this decision. State the problem clearly
in 2-4 sentences without prematurely advocating for a solution.]

### Scope and non-goals

* **In scope:** [Systems, data, teams, environments, and lifecycle stages]
* **Out of scope:** [Explicit exclusions]
* **Assumptions:** [Assumptions that must remain true]
* **Evidence:** [Links to measurements, incidents, requirements, or source files]

## 2. Decision Drivers (Forces and Constraints)

* **Driver 1 (Performance/SLA):** [e.g., P99 latency must stay under 15 ms at
  100k requests/second]
* **Driver 2 (Resource Constraints):** [e.g., target edge nodes have less than
  2 GB RAM available]
* **Driver 3 (Operational Overhead):** [e.g., must not require dedicated
  multi-node cluster management]
* **Driver 4 (Compliance/Security):** [e.g., end-to-end mTLS and no data-at-rest
  persistence on edge]
* **Driver 5 (Team and Delivery):** [Skills, schedule, migration, or support constraints]

## 3. Considered Options

* **Option 1:** [Name of architecture, tool, library, or “do nothing” option]
* **Option 2:** [Name of architecture, tool, library, or “do nothing” option]
* **Option 3:** [Name of architecture, tool, library, or “do nothing” option]

## 4. Evaluation Matrix

Score each option consistently, for example from 1 (poor) to 5 (excellent).
Record evidence or a short rationale in each cell. Weights express relative
importance and must not be mistaken for measured performance.

| Criterion / Driver | Weight (1-5) | Option 1: [Name] | Option 2: [Name] | Option 3: [Name] |
| :--- | :---: | :--- | :--- | :--- |
| **[Driver 1: Performance]** | 5 | [Score / evidence] | [Score / evidence] | [Score / evidence] |
| **[Driver 2: Resource Footprint]** | 4 | [Score / evidence] | [Score / evidence] | [Score / evidence] |
| **[Driver 3: Operational Simplicity]** | 4 | [Score / evidence] | [Score / evidence] | [Score / evidence] |
| **[Driver 4: Ecosystem and Tooling]** | 3 | [Score / evidence] | [Score / evidence] | [Score / evidence] |
| **[Driver 5: Security and Compliance]** | 5 | [Score / evidence] | [Score / evidence] | [Score / evidence] |
| **Weighted total** | — | [Sum] | [Sum] | [Sum] |
| **Suitability** | — | **[High / Medium / Low]** | **[High / Medium / Low]** | **[High / Medium / Low]** |

## 5. Decision Outcome

**Chosen Option:** **[Option X]**, because [concise 1-2 sentence justification
highlighting the primary technical advantage and alignment with the drivers].

### Justification and key differentiators

* **[Key factor 1]:** [Why this distinguishes the chosen option]
* **[Key factor 2]:** [Why alternatives do not meet the constraint as well]
* **[Boundary of the decision]:** [What this decision does not decide]

## 6. Detailed Analysis of Options

### Option 1: [Name]

* **Description:** [Brief architectural summary]
* **Advantages:**
  * (+) [Advantage 1]
  * (+) [Advantage 2]
* **Disadvantages and risks:**
  * (-) [Drawback 1]
  * (-) [Drawback 2]
* **Security considerations:** [Trust boundaries, attack surface, identity,
  secrets, data exposure, abuse cases]
* **Operational considerations:** [Deployment, monitoring, backup, scaling,
  on-call, recovery, and decommissioning]
* **Migration impact:** [Compatibility, data migration, rollback complexity]

### Option 2: [Name]

* **Description:** [Brief architectural summary]
* **Advantages:**
  * (+) [Advantage 1]
  * (+) [Advantage 2]
* **Disadvantages and risks:**
  * (-) [Drawback 1]
  * (-) [Drawback 2]
* **Security considerations:** [Threats and controls]
* **Operational considerations:** [Runtime and support implications]
* **Migration impact:** [Compatibility, migration, and rollback implications]

### Option 3: [Name]

* **Description:** [Brief architectural summary]
* **Advantages:**
  * (+) [Advantage 1]
  * (+) [Advantage 2]
* **Disadvantages and risks:**
  * (-) [Drawback 1]
  * (-) [Drawback 2]
* **Security considerations:** [Threats and controls]
* **Operational considerations:** [Runtime and support implications]
* **Migration impact:** [Compatibility, migration, and rollback implications]

## 7. Security and Privacy Assessment

* **Assets and data classification:** [Public, internal, confidential,
  sensitive, personal, financial, or regulated data]
* **Trust boundaries:** [Ingresses, egresses, service boundaries, and
  administrative boundaries]
* **Threats considered:** [STRIDE, abuse cases, supply-chain risks, and
  failure-induced exposure]
* **Required controls:** [Authentication, authorization, encryption, validation,
  isolation, logging, rate limiting, retention, and key management]
* **Residual risk:** [Risk accepted, owner, expiry/review date]
* **Security review:** [Reviewer, date, findings, and linked issue]

## 8. Consequences and Trade-Offs

### Positive impacts

* [What becomes easier, faster, cheaper, safer, or more reliable]
* [New capability or constraint removed]

### Negative impacts and accepted debt

* [What becomes harder, slower, or more expensive]
* [Technical debt explicitly accepted, owner, and repayment trigger]

### Mitigations and action plan

| Risk or debt | Mitigation / action | Owner | Due date | Tracking issue | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [Risk] | [Action] | [Role/name] | [YYYY-MM-DD] | [Issue] | [Open / Done] |

## 9. Implementation and Validation Plan

* [ ] **Phase 1 — Proof of Concept:** [Validation criteria, benchmark targets,
  security checks, fixtures, and exit criteria]
* [ ] **Phase 2 — Canary Deployment:** [Rollout target, ingress routing,
  observability, abort thresholds, and rollback command]
* [ ] **Phase 3 — Full Cutover and Decommissioning:** [Migration completion,
  decommissioning of the old stack, and evidence to retain]

### Acceptance criteria

* [ ] [Functional or compatibility criterion]
* [ ] [Performance or capacity criterion]
* [ ] [Security, privacy, or compliance criterion]
* [ ] [Operational readiness and runbook criterion]
* [ ] [Documentation, training, and ownership criterion]

### Rollout and rollback

* **Feature flag / control:** [Name, default, and change authority]
* **Rollout increments:** [Percentages, environments, or tenants]
* **Abort thresholds:** [Metric, threshold, observation window]
* **Rollback procedure:** [Link to tested runbook and data-compatibility constraint]
* **Rollback owner:** [Role/name]

## 10. Operational Readiness

* **Ownership:** [Service owner and on-call team]
* **SLOs / SLIs:** [Availability, latency, freshness, correctness, or capacity]
* **Dashboards and alerts:** [Links and alert names]
* **Logging and tracing:** [Required fields, correlation, retention]
* **Backup and recovery:** [Backup, restore test, RPO, and RTO]
* **Runbooks:** [Links to triage, deployment, incident, and recovery procedures]
* **Capacity plan:** [Limits, scaling trigger, and load-test evidence]

## 11. Open Questions and Revisit Triggers

* **Open question:** [Question, owner, and due date]
* **Revisit trigger:** [New evidence, incident, scale threshold, dependency
  change, regulatory change, or review date]
* **Review cadence:** [Date or event that causes this ADR to be reviewed]

## 12. References and Evidence

* [Design document, source file, configuration, benchmark, incident, or ticket]
* [Security review, threat model, or compliance requirement]
* [Deployment plan, runbook, migration script, or test report]
```

## Completion checklist

Before changing the status to **Accepted**, confirm that:

- the decision is stated independently of its implementation details;
- all required metadata is complete, unique, and internally consistent;
- all credible alternatives, including retaining the current design, are
  evaluated with the same scoring scale;
- security, privacy, migration, rollback, and operational ownership are explicit;
- acceptance criteria are measurable and evidence links are reproducible;
- accepted risks have an owner, tracking issue, and revisit trigger; and
- consulted reviewers have recorded approval or unresolved objections;
- `bash LLM/scripts/handler.sh adr update` produces no uncommitted index change;
  and
- no private data, credentials, or unsupported scientific claims are included.

For PEIT, preserve the distinction between receipt observations, analyst
normalization, derived indices, estimates, forecasts, and hypotheses. Record
pipeline-semantic changes in the governance decision log as well as in the
relevant ADR.
