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
- Manual supplier quote capture, destination/currency-matched landed-cost comparison and sample-aware operator-entered supplier scorecards.
- Editable SVG creative studio with five visual styles, five palettes, saved assets, multi-style collections and basic print-size/safe-area checks.
- Persistent A/B marketing experiments with per-variant metrics and descriptive comparison.
- Competitor observation analysis, integrated opportunity scoring from source evidence, competitor observations and unit economics, pricing sensitivity and break-even scenarios.
- Period-filtered P&L reports, Google Trends rank history and order-aware support response drafts.
- Quote-based simulated purchase-order preparation with itemized supplier and shipping costs.
- Simulated order lifecycle with exact amount/currency approval checks. No supplier order is actually placed.
- Campaign metrics: CTR, conversion, CPA and ROAS.
- Finance ledger, manual reconciliation and scenario cash-flow projections.
- Durable jobs, idempotency, retries, interrupted-job recovery and local background processing.
- Automatic daily integrity-checked SQLite backups with seven-backup rotation, manual backup and verified restore commands.
- Dependency-aware, allowlisted agent plans with prior-step output references; no shell execution or arbitrary code execution.

## Local backups

The dashboard creates an integrity-checked SQLite backup at most once per 24 hours and retains the seven newest backups in `data/backups/`. Create or inspect backups manually:

```bash
python -m aureon.cli backup
python -m aureon.cli backups
```

To restore, stop the Aureon server first. The current database is backed up before the selected snapshot replaces it:

```bash
python -m aureon.cli restore data/backups/aureon-YYYYMMDD-HHMMSS-ffffff.sqlite3
```

## Live integrations

### Configure an LLM in the dashboard
Open **Automation & System → AI model settings**. Choose a provider preset (OpenAI, Anthropic, Gemini, OpenRouter, Groq, Together AI, DeepSeek, Mistral, Cerebras, xAI, Fireworks, Perplexity or local Ollama), enter the exact model ID from that provider, add your API key, save, then test the connection. You can also choose **Custom OpenAI-compatible endpoint** for compatible gateways, inference hosts and self-hosted servers. Anthropic and Gemini use their native request formats; OpenAI-compatible services use the chat-completions protocol. The provider determines which model IDs and features are available. Keys are stored in a local `llm_settings.json` file beside the database with owner-only permissions where supported; the settings API never returns the key. Keep the database directory private and do not expose Aureon beyond localhost.

When a model is configured, commerce missions use it to generate listing copy, launch copy, tags and an evidence-bound research analysis. If it is unavailable or returns invalid structured output, the mission reports the problem and falls back to local draft generation. AI output remains a draft and is not verified market evidence.

### Google Trends
Public Trending RSS by country code. Fetch trends in the dashboard, or save unique signals as research-stage opportunity records. Trend attention is not proof of product demand or sales.

### Shopify
Admin GraphQL adapter for connection testing, product catalog reads and creating unpublished DRAFT products after a separate approval request and an explicit approval action in the dashboard. Uses API version 2026-10. Create a custom app on a development store with read_products and write_products scopes. Set AUREON_SHOPIFY_STORE and AUREON_SHOPIFY_ACCESS_TOKEN in the local .env file. No publishing, order placement, inventory mutation, refunds or payments are exposed.

### Printify
Merchant shop and catalog discovery: shops, product blueprints, print providers, variants and shipping data. Set AUREON_PRINTIFY_API_TOKEN in .env. Read-only discovery needs shops.read and catalog.read; artwork upload needs uploads.write; hidden product creation needs products.write. Upload an artwork URL, inspect a blueprint/provider/variant combination, then submit a validated product payload through the separate approval flow. Aureon explicitly sets visible=false so a new product is not shown in the connected sales channel. Publishing, order submission and fulfillment are not enabled.

A provider token being present only means credentials are configured. Use the dashboard's connection check to confirm actual access. Never paste credentials into chat or commit .env.

## API

- GET /health, GET /api/providers, GET /api/trends?geo=IN, POST /api/trends/collect
- GET /api/shopify/connection, GET /api/shopify/products, POST /api/shopify/drafts/approval, POST /api/shopify/drafts
- GET /api/printify/shops, GET /api/printify/blueprints
- GET /api/printify/blueprints/{id}/providers
- GET /api/printify/blueprints/{id}/providers/{provider_id}/variants and /shipping
- POST /api/printify/uploads, POST /api/printify/products/approval, POST /api/printify/products
- POST /api/creative/generate, POST /api/creative/collections, GET /api/creative/assets, POST /api/creative/mockup
- POST /api/research/competitors, POST /api/opportunities/evaluate, POST /api/economics/scenarios, POST /api/economics/break-even
- POST /api/marketing/experiments, POST /api/marketing/experiments/{id}/observations, GET /api/marketing/experiments/{id}
- GET /api/trends/history, GET /api/finance/profit-and-loss
- POST /api/orders/prepare-from-quote
- GET /api/backups, POST /api/backups
- GET /api/overview, GET /api/jobs, GET/POST /api/records, PATCH /api/records/{id}
- POST /api/opportunities/assess
- GET/POST /api/suppliers, POST /api/suppliers/{id}/quotes and /performance, GET /api/suppliers/{id}/scorecard and /api/suppliers/compare
- POST /api/orders and order approval, simulated submission, tracking and refund-review routes
- GET /api/campaigns/metrics, POST /api/campaigns/{id}/metrics
- GET/POST /api/schedules, POST /api/schedules/run-due
- GET/POST /api/approvals, POST /api/approvals/{id}/decision
- GET/POST /api/finance, GET /api/finance/dashboard, POST /api/finance/reconcile, POST /api/finance/forecast
- GET/POST /api/support and support response/note routes, POST /api/support/{id}/contextual-response
- GET/POST /api/marketing/campaigns
- GET /api/agents, POST /api/agents/plans, POST /api/missions, GET /api/missions/{job_id}
- GET /api/command-center, POST /api/commands/interpret

## Important autonomy boundaries
Missions currently orchestrate a fixed, deterministic sequence; they are not yet a general-purpose autonomous AI that can invent and execute arbitrary plans. The optional AI analyst reviews collected context but does not choose tools or control the worker. Supplier quote data remains operator-entered, and external actions stay approval-gated or unavailable.

## Not yet a fully autonomous commerce operator

WooCommerce, Printful and Gelato are not connected. Printify product creation is approval-gated and remains unpublished; Printify order submission and fulfillment are not enabled. Shopify product publication, payment processing, inventory synchronization and order fulfillment are not enabled. Supplier quotes remain manually entered unless separately verified. Customer inboxes, customer messaging, social publishing, ad buying, bank feeds, tax and FX providers are not connected.

External spending, publishing, purchases, refunds and customer commitments remain human-controlled. The server is localhost-only, not a public production API or storefront.

## Verify

Run the complete suite in Termux after pulling the latest commits:

```bash
git pull --ff-only
python -m unittest discover -s tests -v
python -m aureon.cli status
```

Do not treat a committed test as a passing test until it has actually run.
