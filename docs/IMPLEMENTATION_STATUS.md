# Implementation Status

This document distinguishes implemented local workflows, live read-only data access, limited write actions, and external actions that are not enabled.

## Implemented local workspace

- SQLite persistence, event history, durable queue, idempotency, bounded retries and interrupted-job recovery.
- Automatic daily integrity-checked SQLite backups, bounded retention, manual backup and verified restore.
- Product, opportunity, design, listing, supplier, order, support and campaign records.
- Product economics with estimated tax, duty, return and chargeback reserves; POD/dropshipping comparison; pricing sensitivity and break-even order scenarios.
- Evidence-backed competitor observation analysis, integrated opportunity scoring from supplied evidence/observations/unit economics; manual quote comparisons, sample-aware supplier scorecards and quote-based itemized simulated purchase-order preparation. No market-wide competitor crawler is claimed.\n- Keyword-driven public Google News RSS research with source URLs, publisher names, publication timestamps, country targeting, deduplication and persisted research leads; Google Trends attention snapshots remain separate from purchase-demand evidence.
- Local editable SVG creative studio with five styles, five palettes, saved assets, multi-style collections, print-size checks and illustrative flat mockups.
- Persistent A/B marketing experiments with per-variant observations and descriptive comparison; no statistical significance claims or publishing.
- Collected Google Trends snapshot history and rank movement across the latest two saved snapshots.
- Order-aware support response drafts using locally recorded fulfillment status; responses remain unsent.
- Period-filtered, multi-currency P&L reporting that keeps actual and estimated entries separate.
- Dependency-aware supervised agent plans with strict allowlisted task payloads, validated earlier-step references, persisted step outputs, bounded recovery and sequential execution.\n- Objective-driven commerce missions that combine public trend/news discovery, saved supplier quote comparison, local unit economics, product records, editable SVG artwork, listing drafts, launch copy and AI evidence analysis. Mission checkpoints and idempotency keys prevent completed local record/artwork steps from being duplicated after a process interruption.
- Draft generation for design briefs, listings, marketing and support.
- Campaign observations and CTR, conversion, CPA and ROAS calculations.
- Actual-versus-estimated finance ledger, manual reconciliation and scenario cash-flow projections.
- Approval records for sensitive actions, including exact target/amount/currency matching for simulated supplier orders.
- Localhost dashboard and JSON API.
- Background local worker runs while the dashboard server is running. It processes allowlisted local jobs and due one-time schedules. It does not execute arbitrary shell commands or external side effects.

## Live data and provider integrations

### Google Trends public Trending RSS
- Fetch current public trending searches by country code.
- Includes title, traffic label, timestamp, source link and related news where supplied.
- Can persist deduplicated search signals as research-stage opportunities.
- This is attention data, not validated product demand, sales or profitability.

### Shopify Admin GraphQL
- Connection test against a configured store.
- Read product catalog.
- Create an unpublished DRAFT product from the dashboard after a separate approval request and explicit approval action.
- Uses API version 2026-10 and requires read_products and write_products scopes.
- No product publishing, order placement, inventory mutation, refunds or payments.

### Printify API
- Read merchant shops.
- Read product blueprints, print providers, variants and shipping information.
- Upload artwork from a public HTTPS URL and create a product hidden from connected sales channels with explicit one-time approval.
- Product payload validation checks variant references, print areas, uploaded image IDs and numeric positioning values. The provider request explicitly sets visible=false.
- Requires shops.read and catalog.read for discovery, uploads.write for artwork upload, and products.write for product creation.
- Publishing, order submission and fulfillment are not enabled.

Provider code is committed, but credentials must be configured locally and each connection must be tested against the user's own development account. A configured token is not proof of a successful connection.

## Not implemented / not claimed complete

- WooCommerce, Printful and Gelato adapters.
- Printify order submission, mockup generation and fulfillment.
- Shopify product publication, order/inventory synchronization, payment or refund actions.
- Supplier purchasing, carrier tracking, returns, or actual fulfillment.
- External AI image generation, raster export, production mockups, and provider-specific print-file QA. Local SVG generation and basic size/safe-area checks are implemented.
- Connected customer inboxes, sending customer replies, social publishing or ad buying.
- Bank/payment feeds, live tax and FX providers, accounting exports.
- Independent marketplace crawling and verified competitor price/saturation collection. Competitor analysis accepts supplied observations only.\n- Verified supplier stock, quality, delivery performance or live quotes unless a provider integration supplies them. Manual supplier quotes remain unverified.\n- Cloud execution, remote access or production hosting. The local mission/agent worker checkpoints supported local steps; ambiguous external writes remain approval-gated and are not automatically replayed.
- Fully autonomous commercial decision-making. External spending, publishing and customer commitments remain human-controlled.

## Security and operation

- Server binds to localhost only.
- .env is ignored by Git and simple AUREON_ key/value entries are loaded locally. Never commit credentials or customer data.
- Start with development/test stores and minimum required provider scopes.
- Shopify draft creation is an explicit dashboard action. No publishing action is exposed.
- Printify catalog discovery is read-only; artwork upload and hidden product creation are explicit write actions. Publishing and order submission are not enabled.

## Verification

The test suite covers the local core, workflows, trend collection/history, keyword research, worker retry/recovery behavior, Shopify and Printify validation, creative assets, competitor analysis, pricing scenarios, P&L, A/B experiments, backups and dependency-aware agent plans. The newest additions have not been executed in the target Termux environment. Run:

    git pull --ff-only
    python -m unittest discover -s tests -v

A successful commit is not a successful test run. Verify provider connections only after setting credentials in your local .env.

## Commands

    python -m aureon.cli init
    python -m aureon.cli status
    python -m aureon.cli run

The server starts the dashboard and local background worker together. Use Ctrl+C to stop both.
