# Vercyra Security: Project Overview and Proposal

## Executive summary

Vercyra Security is an early-stage security-monitoring prototype. The repository contains a React dashboard, Python network-monitoring code, a separate file-watcher and quarantine prototype, and preliminary subscription-billing code.

The current implementation is suitable for development and controlled testing, not yet for production use with customers. It does not currently implement AI agents, comprehensive antivirus detection, or a production firewall.

## Project purpose

The product direction is a dashboard where a small organization can review selected security events from systems it owns or is authorized to monitor. A future service could pair the dashboard with customer-installed sensors, centralize their alerts, and offer plan-based features.

This is a proposed direction, not a description of a finished multi-customer service.

## Repository components

| Path | Responsibility | Current state |
| --- | --- | --- |
| `frontend/src/SecurityDashboard.jsx` | Dashboard UI for authentication, metrics, events, capture status, billing, and exports | UI exists; depends on a configured, available backend |
| `frontend/src/api.js` | Browser API calls | Frontend integration layer |
| `frontend/vite.config.js` | Vite build and development-server configuration | Supports local development and configurable deployment base paths |
| `frontend/functions/api/[[path]].js` | Cloudflare Pages Function forwarding `/api/*` requests to a separately hosted HTTPS backend | Proxy code exists; Pages and backend still need deployment and configuration |
| `vercyra_security_api.py` | Local HTTP API for monitoring, dashboard, billing, and export endpoints | Development server binds to loopback; do not expose directly to the Internet |
| `passenger_wsgi.py` | WSGI application with password-based dashboard authentication and API routes | Separate deployment path; packet capture explicitly unavailable in this app |
| `vercyra_network_security.py` | Scapy packet monitor, SQLite event storage, threshold alerts, and optional SMTP notifications | Basic network-monitoring prototype |
| `vercyra_business_security_suite.py` | File watcher, SHA-256 checks, quarantine, and optional SMTP notifications | Separate file-watcher prototype; not connected to dashboard event storage |
| `vercyra_config.py` | Loads environment configuration | Configuration helper; secrets must stay outside frontend code and version control |
| `requirements.txt` | Python package requirements | Includes Scapy, watchdog, and python-dotenv |
| `SECURITY_DASHBOARD.md` | Local usage and deployment notes | Main dashboard/deployment reference |
| `DEPLOYMENT.md` | General deployment notes | Check against the current Python implementation; portions describe a separate Node backend |

## Current functionality

### Dashboard

The React dashboard is intended to display network activity, alerts, capture state, billing information, and CSV exports. It requires a reachable backend with compatible routes and authentication configuration.

### Network monitoring

`vercyra_network_security.py` uses Scapy to observe IP traffic accessible to the host running it. It records source and destination IP metadata and tracks packet counts by source. It creates a threshold alert when a source exceeds 100 packets during a 10-second window.

This is a basic rate alert, not a firewall: the threshold alert does not itself block traffic. Capture visibility depends on host permissions and network placement. Packet capture should only be enabled on systems and networks the operator is authorized to monitor.

The monitor stores event metadata in a local SQLite database and does not intentionally store packet payloads. Network event records older than 30 days are periodically removed.

### File watching and quarantine

`vercyra_business_security_suite.py` watches a directory, calculates file hashes, compares them with a small built-in sample signature list, and moves matches to a quarantine directory. It can send email alerts when SMTP is configured.

This is not a complete antivirus engine. The sample signature list is limited and cannot identify most malware. Quarantine can disrupt files, so test it only in a disposable directory until its behavior and recovery process have been reviewed. This process is separate from the dashboard and is not automatically started by the web application.

### Authentication and billing

The WSGI application supports a shared dashboard password and signed session cookie. This is not a full user-account system and does not provide customer or organization isolation.

The API contains PayPal subscription and webhook scaffolding for Starter, Pro, and Business feature tiers. Actual plans and prices must be configured with the payment provider. Local billing simulators, when explicitly enabled for sandbox testing, do not create real subscriptions or take payments.

Billing state is currently global in the SQLite database rather than associated with individual customer accounts. The Business tier advertises extended retention in feature metadata, but network events are currently cleaned up after 30 days regardless of tier.

## Deployment status and constraints

- The frontend has Cloudflare Pages build/proxy configuration, but this does not mean a Pages project or production site has been deployed.
- Cloudflare Pages hosts the frontend, not the Python API, SQLite database, or continuous file watcher.
- The development HTTP API binds to `127.0.0.1`; do not expose it directly to the public Internet.
- The WSGI app explicitly reports packet capture as unavailable.
- SQLite data must be placed on durable storage with backups if used on a remote host.
- The file watcher is not currently integrated with the API's event database.
- Live billing requires real provider credentials, plan IDs, public HTTPS URLs, a verified webhook, and lifecycle testing. Keep checkout in sandbox until those steps pass.
- The current shared-password authentication and global billing state are not sufficient for a multi-customer SaaS product.

## Strengths

- A browser dashboard and API integration have been started.
- Network metadata collection and threshold alerting are implemented.
- The monitor is designed not to retain packet payloads.
- There is an initial file-monitoring and quarantine workflow.
- Authentication, subscription, webhook, and deployment foundations exist.
- Frontend production builds and the Pages API proxy have been tested locally.

## Limitations and risks

- Detection coverage is narrow and should not be marketed as comprehensive protection.
- Rate alerts do not block or mitigate traffic.
- The file signature list is only a small demonstration and may miss threats.
- Quarantine actions need careful safeguards and recovery procedures.
- Network visibility is limited to traffic available to each monitoring host.
- The monitoring processes, backend, and dashboard are not yet a unified customer product.
- Authentication, authorization, tenant isolation, durable storage, operations, and billing need substantial work before a commercial launch.
- No AI-agent or AI-based detection implementation is currently present.

## Product proposal

### Proposed product

Develop Vercyra into a security-event monitoring dashboard for a narrowly defined group of small organizations. Customers would connect explicitly authorized sensors to a secure backend, review events in an organization-specific dashboard, and optionally use plan-based reporting features.

### Initial customer focus

Begin with one clearly defined customer profile—for example, small businesses managing a few authorized computers or a small office network. Interview prospective users and run a limited pilot before expanding the feature set.

### Suggested first release

1. Individual user accounts and organization membership.
2. Strict organization-level data isolation and authorization.
3. Authenticated sensor enrollment, event reporting, revocation, and updates.
4. A documented and deliberately limited set of event types and alerts.
5. A dashboard with event search, filtering, and exports.
6. Durable data storage, backups, health monitoring, and audit trails.
7. A safe sensor setup/removal workflow with explicit authorization.
8. Billing only after account, tenant, and subscription lifecycle handling is reliable.

### Development phases

**Phase 1: Stabilize the prototype**
- Review code and deployment artifacts.
- Keep secrets, `.env` files, local Python environments, databases, logs, and quarantined files out of source control and deployments.
- Document detection limits and test alert and quarantine behavior.
- Decide whether file watching belongs in the first release.

**Phase 2: Build the service foundation**
- Implement users, organizations, roles, and tenant isolation.
- Design a persistent backend and database schema.
- Add sensor authentication, authorization, audit events, and retention controls.
- Deploy only behind HTTPS with secure secret storage and operational monitoring.

**Phase 3: Pilot**
- Test setup, data separation, event delivery, dashboard behavior, backups, and recovery.
- Run a small pilot with written authorization for every monitored system and network.
- Measure alert usefulness, false positives, and operational burden.

**Phase 4: Commercial readiness**
- Complete security and privacy reviews.
- Test payment-provider sandbox flows, including activation, renewal, cancellation, failure, and webhook verification.
- Enable live payments only after the production service and webhook are verified.
- Publish accurate product limits, privacy terms, support procedures, and pricing.

## Success measures

- Customers can install and remove sensors safely.
- Events are visible only to the correct organization.
- Authentication and authorization behave consistently.
- Alerts are understandable and their false-positive rates are measured.
- Data can be backed up and restored.
- Subscription state follows verified payment-provider events.
- Customers understand exactly what the product detects and what it does not.

## Recommended current product description

> Vercyra Security is an early-stage security-monitoring prototype with a React dashboard, a Python network-rate alert monitor, an experimental file-hash quarantine watcher, and initial billing scaffolding. It is intended for development and controlled testing. It is not a complete antivirus product, production firewall, AI security agent, or fully deployed multi-customer SaaS service.

## Security and publication checklist

- Monitor only systems and networks owned by the operator or explicitly authorized by their owners.
- Never expose the local development API directly to the Internet.
- Do not publish passwords, API keys, payment credentials, SMTP credentials, session secrets, `.env` files, database contents, security logs, or quarantine files.
- Review version-control changes before deploying; do not blindly publish the entire working directory.
- Use sandbox billing until authentication, HTTPS, webhook delivery, and subscription lifecycle handling have been verified.
- Treat network events and IP addresses as sensitive information.

## Suggested next steps

1. Review and clean the repository contents before pushing or deploying.
2. Deploy the frontend to Cloudflare Pages.
3. Deploy the backend separately to a host with HTTPS, persistent compute, and durable storage.
4. Connect the Pages proxy to the backend and verify health, login, dashboard, logout, and exports.
5. Design the customer-side sensor and tenant-isolated event pipeline before onboarding customers.
6. Complete security, privacy, reliability, and payment testing before a commercial launch.

This document describes the repository's current implementation and a proposed direction. It does not claim that the site, backend, live payments, or customer operations are deployed or production-ready.
