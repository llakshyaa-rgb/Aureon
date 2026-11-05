# Implementation Status

This document distinguishes implemented local workflows, live read-only data access, limited write actions, and external actions that are not enabled.

## Implemented local workspace

- SQLite persistence, event history, durable queue, idempotency, bounded retries and interrupted-job recovery.
- Product, opportunity, design, listing, supplier, order, support and campaign records.
- Product economics with estimated tax, duty, return and chargeback reserves; POD/dropshipping comparison; pricing sensitivity and break-even order scenarios.
- Evidence-backed competitor observation analysis, manual quote comparisons and quote-based itemized simulated purchase-order preparation.
- Local editable SVG creative studio with five styles, five palettes, saved assets, multi-style collections, print-size checks and illustrative flat mockups.
- Persistent A/B marketing experiments with per-variant observations and descriptive comparison; no statistical significance claims or publishing.
- Collected Google Trends snapshot history and rank movement across the latest two saved snapshots.
- Order-aware support response drafts using locally recorded fulfillment status; responses remain unsent.
- Period-filtered, multi-currency P&L reporting that keeps actual and estimated entries separate.
- Dependency-aware supervised agent plans with validated earlier-step references and sequential execution.
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
- Crash-resumable dependency-aware agent step checkpoints, cloud execution, remote access or production hosting. Agent plans run as single-attempt jobs to avoid replaying already-created local records.
- Fully autonomous commercial decision-making. External spending, publishing and customer commitments remain human-controlled.

## Security and operation

- Server binds to localhost only.
- .env is ignored by Git and simple AUREON_ key/value entries are loaded locally. Never commit credentials or customer data.
- Start with development/test stores and minimum required provider scopes.
- Shopify draft creation is an explicit dashboard action. No publishing action is exposed.
- Printify catalog discovery is read-only; artwork upload and hidden product creation are explicit write actions. Publishing and order submission are not enabled.

## Verification

The repository includes tests for the local core, workflows, trend collection/history, worker retry behavior, Shopify validation, Printify product payload validation, creative assets, competitor analysis, pricing scenarios, P&L and dependency-aware agent plans. The latest additions have not been run in the target Termux environment. Run:

    git pull --ff-only
    python -m unittest discover -s tests -v

A successful commit is not a successful test run. Verify provider connections only after setting credentials in your local .env.

## Commands

    python -m aureon.cli init
    python -m aureon.cli status
    python -m aureon.cli run

The server starts the dashboard and local background worker together. Use Ctrl+C to stop both.
