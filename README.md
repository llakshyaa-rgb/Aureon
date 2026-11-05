# Aureon

Aureon is a local-first commerce operations workspace with persistent SQLite workflows, a browser dashboard, a JSON API, and a first live public-data source.

## Run on Termux or Linux

Requires Python 3.10+.

```bash
git clone https://github.com/llakshyaa-rgb/Aureon.git
cd Aureon
python -m aureon.cli init
python -m unittest discover -s tests -v
python -m aureon.cli run
```

Open http://127.0.0.1:8787 on the same device. Stop with Ctrl+C.

## What works locally

- Persistent product, opportunity, design, listing, supplier, order, support and campaign records.
- Product economics and POD/dropshipping comparisons from supplied cost assumptions.
- Supplier quote capture and destination/currency-matched landed-cost comparison. Quotes are not supplier-verified.
- Design, listing, marketing and support drafts.
- Simulated order lifecycle with amount/currency-bound approvals. Submission records are explicitly simulated.
- Campaign metric capture and CTR, conversion, CPA and ROAS calculations.
- Finance ledger, manual reconciliation and scenario cash-flow projections.
- Persistent jobs, idempotency, bounded retries, crash recovery and manually ticked schedules.
- Allowlisted agent task plans and a read-only command center.
- Interactive dashboard actions for saving product records and finance transactions.

## Live public data

- **Google Trends public Trending RSS:** use the dashboard's Live opportunity discovery panel or GET /api/trends?geo=IN. Country code is configurable.
- Trend results include source links, related news, traffic labels and fetch timestamps.
- Trending searches are attention signals only. They do not establish product demand, sales, competitor saturation, supplier inventory or profitability.

## API

- GET /health, GET /api/providers, GET /api/trends?geo=IN
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

## Integration status — be precise

Aureon is **not a finished autonomous dropshipping/POD operator**. Shopify, WooCommerce, Printify, Printful, Gelato, payment providers, carriers, customer inboxes, ad accounts and supplier order APIs are not connected yet. Supplier quote data is manually entered; order submission and fulfillment are simulated; no money is spent, no refunds are issued, and no listings or customer messages are published.

The local application is usable without credentials. Real external commerce actions require provider adapters, credentials, provider-side testing and explicit human approvals. Do not treat public trend signals or local records as verified commercial data.

The server binds to localhost only. It is not a public API or production storefront. Never commit credentials or customer data.
