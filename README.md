# Aureon

A local-first AI commerce operations platform for researching opportunities, creating products, comparing print-on-demand with dropshipping, and eventually managing publishing, fulfillment, marketing, and analytics.

## Current milestone

The first foundation provides a phone-friendly Python runtime, SQLite persistence, a durable job queue, a local HTTP API, provider contracts, and tests. Product discovery, artwork generation, supplier/store integrations, and real order operations are roadmap items, not features claimed to be complete.

## Design principles

- Local-first and cloud-ready: develop on Android/Termux; move scheduled workers to cloud later.
- Safe by default: mock mode, no real purchases, no live order submission, localhost binding.
- Evidence before action: preserve source links and separate facts from AI hypotheses.
- Human approval for spending, public publishing, refunds, and supplier commitments.
- Provider-neutral: POD, dropshipping, storefronts, trend sources, and AI models are adapters.
- Recoverable: persistent jobs, bounded retries, event history, and idempotency keys.
- No secrets in Git.

## Run on Termux or Linux

Requires Python 3.10+. The foundation uses only the Python standard library.

    git clone https://github.com/llakshyaa-rgb/Aureon.git
    cd Aureon
    python -m aureon.cli init
    python -m aureon.cli run

Open http://127.0.0.1:8787 on the same device. Stop with Ctrl+C.

Useful commands:

    python -m aureon.cli status
    python -m unittest discover -s tests -v

## Local API

- GET /health — health and mode.
- GET /api/overview — persisted job counts.
- GET /api/jobs — recent jobs.
- POST /api/jobs — enqueue a job with JSON such as {"kind":"research.scan","payload":{}}.

This is a local development control plane, not a production storefront or public API. Do not expose it to the internet until authentication, authorization, rate limits, CSRF protections, and deployment hardening exist.

## Planned capabilities

1. Global trend, niche, demand, and competitor research.
2. Opportunity scoring with evidence, saturation, shipping, fees, production cost, and margin estimates.
3. POD-versus-dropshipping decision engine.
4. Original design briefs, artwork workflows, mockups, and collections.
5. Supplier/catalog discovery and product normalization.
6. SEO listings, pricing suggestions, and draft publishing.
7. Order intake, supplier fulfillment, tracking, exception handling, and customer-service assistance.
8. Marketing experiments, performance analytics, and persistent business memory.

Each integration will be implemented only after checking its API, commercial terms, regional availability, and operating costs.

## Repository map

- aureon/config.py — runtime settings.
- aureon/db.py — SQLite schema and event persistence.
- aureon/jobs.py — durable queue and state transitions.
- aureon/server.py — local HTTP API and status page.
- aureon/providers/base.py — future integration contracts.
- docs/ — architecture and safety rules.

## Account and business eligibility

Aureon will not bypass marketplace eligibility, identity checks, age requirements, payment-provider rules, tax obligations, or supplier terms. Use accurate account information and an eligible adult account holder wherever a platform requires one. Start with mock data and manual review before connecting real commerce accounts.

## License

MIT. See LICENSE.
