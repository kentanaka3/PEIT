# Security policy

## Reporting

Do not report vulnerabilities in public issues when they could expose
credentials, private receipt data, or an exploitable weakness. Contact the
repository maintainers through the private security-reporting mechanism
configured for the hosting organization. No public security email or PGP key
is configured in this repository; do not invent one.

Include the affected commit or path, reproduction steps using synthetic data,
impact, and a suggested mitigation. Redact personal data, tokens, hostnames,
and private URLs.

## Data handling

Treat receipt rows, source files, audit ledgers, and external LLM inputs as
potentially sensitive. Keep restricted data outside Git, use approved storage,
and never commit `.env` files, credentials, raw catalogs, waveforms, or
checkpoints. The current prototype has no network-facing service or
authentication layer.

## Response boundary

Maintainers should acknowledge reports, reproduce safely, assess impact,
prepare a minimal fix, and document the resolution. Severity targets and a
coordinated disclosure schedule remain project decisions recorded in
`LLM/00_governance/open_questions.md`.
