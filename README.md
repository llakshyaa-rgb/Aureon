# Aureon

A local-first commerce operations workspace for product research, POD/dropshipping economics, creative and listing drafts, order simulation, marketing measurement and finance records.

## Scope versus implementation
The full target scope is documented in docs/FEATURES.md and docs/ROADMAP.md. Those documents describe the intended product, not completed integrations. See docs/IMPLEMENTATION_STATUS.md for the honest current state.

## Current local capabilities
- Termux-friendly Python runtime; no third-party runtime dependencies.
- SQLite persistence, event history, durable jobs, idempotency, bounded retries and interrupted-job recovery.
- Localhost-only dashboard and JSON API.
- Evidence-backed opportunity records using analyst-supplied signals and traceable evidence.
- Supplier profiles, manually entered quotes and destination/currency-matched landed-cost comparisons.
- Unit economics and POD/dropshipping comparison.
- Structured design briefs, listing drafts, marketing drafts and support triage.
- Order simulation, approval-gated recording of supplier submission and tracking updates.
- Campaign metric capture and performance calculations.
- Persistent scheduled jobs with manual due-job enqueue.
- Actual-versus-estimated finance ledger and currency-separated summaries.

Not connected: live trend sources, supplier catalogs, image-generation services, stores/marketplaces, fulfillment providers, customer inboxes, social/ad platforms, payment providers, or tax/FX feeds.

## Run on Termux or Linux
Requires Python 3.10+.

    git clone https://github.com/llakshyaa-rgb/Aureon.git
    cd Aureon
    python -m aureon.cli init
    python -m unittest discover -s tests -v
    python -m aureon.cli status
    python -m aureon.cli tick
    python -m aureon.cli work
    python -m aureon.cli run

Open http://127.0.0.1:8787 on the same device. Stop with Ctrl+C.

## API overview
- GET /health, GET /api/overview, GET /api/jobs
- GET/POST /api/records, PATCH /api/records/{id}
- POST /api/opportunities/assess
- GET/POST /api/suppliers, POST /api/suppliers/{id}/quotes, GET /api/suppliers/compare?product_type=...&destination=...&currency=...
- POST /api/orders, POST /api/orders/{id}/approval, POST /api/orders/{id}/submit, POST /api/orders/{id}/tracking
- GET /api/campaigns/metrics, POST /api/campaigns/{id}/metrics
- GET/POST /api/schedules, POST /api/schedules/run-due
- GET/POST /api/approvals, POST /api/approvals/{id}/decision
- GET/POST /api/finance, POST /api/jobs

The server binds to localhost only. It is not a public API or production storefront.

## Safety
Mock mode only. Supplier submissions are simulated records; no external order is placed. No live purchases, supplier orders, ad spend, refunds, public listings or customer messages. Credentials and private business data must never be committed. Respect marketplace, payment-provider, tax, identity and age requirements.
