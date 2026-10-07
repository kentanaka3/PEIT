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
and never commit `.env` files, credentials, raw catalogs, personal receipts,
transaction ledgers, or checkpoints. The prototype provides an optional local HTTP
REST synchronization daemon (`peit --serve`) intended strictly for local-network
or loopback synchronization with the mobile client; it currently implements no
authentication or encryption layer and must not be exposed to untrusted networks.

## Response boundary

Maintainers should acknowledge reports, reproduce safely, assess impact,
prepare a minimal fix, and document the resolution.
