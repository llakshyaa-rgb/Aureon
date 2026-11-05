# Aureon

Aureon is a local-first commerce operations workspace for research, product economics, supplier comparison, creative/listing drafts, store catalog work, support, marketing, analytics and finance.

It runs on Termux/Android or Linux with Python and SQLite. The dashboard binds to localhost.

## Run

```bash
git clone https://github.com/llakshyaa-rgb/Aureon.git
cd Aureon
cp .env.example .env
python -m aureon.cli init
python -m unittest discover -s tests -v
python -m aureon.cli run
```

Open http://127.0.0.1:8787 on the same device. Stop with Ctrl+C. The dashboard starts a background worker that processes allowlisted local jobs and due one-time schedules while the server is running.

## Local capabilities

- Persistent product, opportunity, design, listing, supplier, order, support and campaign records.
- Unit economics and POD/dropshipping comparisons from explicit cost assumptions.
- Manual supplier quote capture and destination/currency-matched landed-cost comparison.
- Design, listing, marketing and support drafts.
- Simulated order lifecycle with exact amount/currency approval checks. No supplier order is actually placed.
- Campaign metrics: CTR, conversion, CPA and ROAS.
- Finance ledger, manual reconciliation and scenario cash-flow projections.
- Durable jobs, idempotency, retries, interrupted-job recovery and local background processing.
- Allowlisted agent plans; no shell execution or arbitrary code execution.

## Live integrations

### Google Trends
Public Trending RSS by country code. Fetch trends in the dashboard, or save unique signals as research-stage opportunity records. Trend attention is not proof of product demand or sales.

### Shopify
Admin GraphQL adapter for connection testing, product catalog reads and creating unpublished DRAFT products after an explicit dashboard confirmation. Uses API version 2026-10. Create a custom app on a development store with read_products and write_products scopes. Set AUREON_SHOPIFY_STORE and AUREON_SHOPIFY_ACCESS_TOKEN in the local .env file. No publishing, order placement, inventory mutation, refunds or payments are exposed.

### Printify
Read-only merchant shop and catalog discovery: shops, product blueprints, print providers, variants and shipping data. Set AUREON_PRINTIFY_API_TOKEN in .env with shops.read and catalog.read scopes. Product creation, artwork upload and order submission are not enabled.

A provider token being present only means credentials are configured. Use the dashboard's connection check to confirm actual access. Never paste credentials into chat or commit .env.

## API

- GET /health, GET /api/providers, GET /api/trends?geo=IN, POST /api/trends/collect
- GET /api/shopify/connection, GET /api/shopify/products, POST /api/shopify/drafts
- GET /api/printify/shops, GET /api/printify/blueprints
- GET /api/printify/blueprints/{id}/providers
- GET /api/printify/blueprints/{id}/providers/{provider_id}/variants and /shipping
- GET /api/overview, GET /api/jobs, GET/POST /api/records, PATCH /api/records/{id}
- POST /api/opportunities/assess
- GET/POST /api/suppliers, POST /api/suppliers/{id}/quotes, GET /api/suppliers/compare
- POST /api/orders and order approval, simulated submission, tracking and refund-review routes
- GET /api/campaigns/metrics, POST /api/campaigns/{id}/metrics
- GET/POST /api/schedules, POST /api/schedules/run-due
- GET/POST /api/approvals, POST /api/approvals/{id}/decision
- GET/POST /api/finance, GET /api/finance/dashboard, POST /api/finance/reconcile, POST /api/finance/forecast
- GET/POST /api/support and support response/note routes
- GET/POST /api/marketing/campaigns
- GET /api/agents, POST /api/agents/plans
- GET /api/command-center, POST /api/commands/interpret

## Not yet a fully autonomous commerce operator

WooCommerce, Printful and Gelato are not connected. Printify product creation and fulfillment are not enabled. Shopify product publication, payment processing, inventory synchronization and order fulfillment are not enabled. Supplier quotes remain manually entered unless separately verified. Customer inboxes, customer messaging, social publishing, ad buying, bank feeds, tax and FX providers are not connected.

External spending, publishing, purchases, refunds and customer commitments remain human-controlled. The server is localhost-only, not a public production API or storefront.

## Verify

Run the complete suite in Termux after pulling the latest commits:

```bash
git pull --ff-only
python -m unittest discover -s tests -v
python -m aureon.cli status
```

Do not treat a committed test as a passing test until it has actually run.
