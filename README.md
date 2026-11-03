# Aureon

A local-first AI commerce operations platform for researching opportunities, creating products, comparing print-on-demand with dropshipping, and eventually managing publishing, fulfillment, marketing, and analytics.

## Current milestone

The foundation includes a Termux-friendly Python runtime, SQLite persistence, a durable job queue with bounded retries and startup crash recovery, a localhost HTTP dashboard/API, provider contracts, transparent opportunity scoring, and unit economics for comparing commerce channels. External providers and live commerce actions are not implemented yet.

## Run on Termux or Linux

Requires Python 3.10+. No third-party Python packages are required.

    git clone https://github.com/llakshyaa-rgb/Aureon.git
    cd Aureon
    python -m aureon.cli init
    python -m unittest discover -s tests -v
    python -m aureon.cli run

Open http://127.0.0.1:8787 on the same device. Stop with Ctrl+C.

## Intelligence tools

The economics module calculates estimated unit costs, fees, profit, margin, and break-even advertising cost. It can compare POD and dropshipping offers in the same currency.

The opportunity scorer combines normalized 0-100 signals for demand, trend, margin, competition, shipping, and evidence confidence. Higher competition scores mean lower saturation. Each weighted contribution is returned for inspection.

These are decision-support calculations, not sales forecasts. Taxes, duties, returns, foreign exchange, and unknown fees must be added as explicit costs when known.

## Local API

- GET /health — health and mode.
- GET /api/overview — job counts.
- GET /api/jobs — recent jobs.
- POST /api/jobs — enqueue a job with JSON such as {"kind":"research.scan","payload":{}}.

The server binds to localhost only. It is not a public API or production storefront.

## Roadmap

1. Evidence-backed trend and competitor research connectors.
2. Normalized product and supplier catalogs with destination-specific shipping quotes.
3. POD-versus-dropshipping recommendations using sourced quotes and economics.
4. Original design briefs, artwork workflows, and mockups.
5. Draft listings, SEO, and storefront adapters.
6. Order intake, approval-gated fulfillment, tracking, customer-service assistance.
7. Marketing experiments and performance analytics.
8. Optional cloud workers and webhooks, with the phone as the control surface.

## Safety

Mock mode only. No live purchases, supplier orders, ad spend, refunds, or public listings. Credentials and local business data must never be committed. Respect marketplace, payment-provider, tax, identity, and age requirements.

See docs/ARCHITECTURE.md and docs/SAFETY.md.
