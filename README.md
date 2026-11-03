# Aureon

A local-first commerce operations workspace for product research, POD/dropshipping economics, creative and listing drafts, simulated order operations, campaign measurement and finance records.

## Current implemented local workflows
- Python/SQLite runtime, durable jobs, idempotency, bounded retries, crash recovery and event history.
- Localhost-only dashboard and JSON API.
- Evidence-backed opportunity intake and weighted scoring using operator-provided research.
- Supplier profiles, manual quotes, destination/currency-matched landed-cost comparison and quote-age labels.
- Unit economics and POD/dropshipping comparison with validated numeric inputs.
- Structured design briefs, listing drafts, marketing drafts and support-ticket triage.
- Simulated orders with amount/currency-bound one-time approval and fulfillment-state tracking.
- Timestamped campaign observations and CTR, conversion, CPA and ROAS calculations.
- Persistent scheduled jobs with idempotent atomic enqueue via manual tick.
- Currency-separated actual/estimated finance ledger and approval records.

## Important boundaries
This is a local mock-mode workspace, not a live dropshipping/POD business operator yet. No live trend APIs, supplier catalogs, image-generation service, marketplace/store publishing, supplier ordering, carrier integrations, customer inbox, social/ad publishing, payments, tax or FX provider is connected. Quotes and research are operator-supplied. ROAS is not profit. Nothing buys, publishes, messages customers or spends money automatically.

See docs/FEATURES.md and docs/ROADMAP.md for the target product scope, and docs/IMPLEMENTATION_STATUS.md for implementation boundaries and verification status.

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

## API
- GET /health, GET /api/overview, GET /api/jobs
- GET/POST /api/records, PATCH /api/records/{id}
- POST /api/opportunities/assess
- GET/POST /api/suppliers, POST /api/suppliers/{id}/quotes, GET /api/suppliers/compare
- POST /api/orders, POST /api/orders/{id}/approval, POST /api/orders/{id}/submit, POST /api/orders/{id}/tracking
- GET /api/campaigns/metrics, POST /api/campaigns/{id}/metrics
- GET/POST /api/schedules, POST /api/schedules/run-due
- GET/POST /api/approvals, POST /api/approvals/{id}/decision
- GET/POST /api/finance, POST /api/jobs

The server binds to localhost only; it is not a public API or production storefront.

## Safety
Mock mode only. Supplier submissions are simulated records; no external order is placed. No live purchases, supplier orders, ad spend, refunds, public listings or customer messages. Never commit credentials or private business data. Respect marketplace, payment-provider, tax, identity and age requirements.
