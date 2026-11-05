# Implementation Status

This document distinguishes implemented local workflows, live read-only provider integrations, and external actions that are not enabled.

## Implemented local workspace

- SQLite persistence, event history, durable queue, idempotency, bounded retries and interrupted-job recovery.
- Product, opportunity, design, listing, supplier, order, support and campaign records.
- Product economics, POD/dropshipping comparison, manual supplier quote capture and landed-cost comparison.
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
- Requires a personal access token with shops.read and catalog.read.
- Product creation, artwork uploads, order submission and fulfillment are not enabled.

Provider code is committed, but credentials must be configured locally and each connection must be tested against the user's own development account. A configured token is not proof of a successful connection.

## Not implemented / not claimed complete

- WooCommerce, Printful and Gelato adapters.
- Printify product creation, artwork upload, mockup generation or order submission.
- Shopify product publication, order/inventory synchronization, payment or refund actions.
- Supplier purchasing, carrier tracking, returns, or actual fulfillment.
- AI image generation, asset management or print-ready QA.
- Connected customer inboxes, sending customer replies, social publishing or ad buying.
- Bank/payment feeds, live tax and FX providers, accounting exports.
- Dependency-aware multi-agent orchestration, cloud execution, remote access or production hosting.
- Fully autonomous commercial decision-making. External spending, publishing and customer commitments remain human-controlled.

## Security and operation

- Server binds to localhost only.
- .env is ignored by Git and simple AUREON_ key/value entries are loaded locally. Never commit credentials or customer data.
- Start with development/test stores and minimum required provider scopes.
- Shopify draft creation is an explicit dashboard action. No publishing action is exposed.
- Printify integration is read-only.

## Verification

The repository includes tests for the local core, workflows, live trend input validation, Shopify adapter validation and Printify adapter validation. The latest additions have not been run in the target Termux environment. Run:

    git pull --ff-only
    python -m unittest discover -s tests -v

A successful commit is not a successful test run. Verify provider connections only after setting credentials in your local .env.

## Commands

    python -m aureon.cli init
    python -m aureon.cli status
    python -m aureon.cli run

The server starts the dashboard and local background worker together. Use Ctrl+C to stop both.
