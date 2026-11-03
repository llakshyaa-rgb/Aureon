# Aureon

A local-first AI commerce operations platform for worldwide product discovery, print-on-demand (POD), dropshipping, creative production, publishing, fulfillment, marketing, customer support and business intelligence.

## The complete vision
Aureon is designed to become an autonomous commerce operator: research opportunities, compare suppliers and business models, create products and collections, prepare listings, coordinate orders, support customers, measure real profitability and improve decisions from recorded outcomes.

The complete agreed scope is documented in docs/FEATURES.md and docs/ROADMAP.md. The roadmap is the target product scope—not a claim that all features already work.

## Current implementation
- Termux-friendly Python runtime with no third-party runtime dependencies.
- SQLite persistence and event history.
- Durable jobs with idempotency, bounded retries and startup recovery.
- Localhost-only HTTP dashboard/API.
- Explainable opportunity scoring.
- POD versus dropshipping unit-economics calculations.
- Local workspace records for opportunities, products, design briefs, listings, orders, support tickets, campaigns, suppliers and customers.\n- Scoped one-time approval records for sensitive actions.\n- Actual-versus-estimated finance ledger and currency-separated summaries.\n- Automated tests for core queue, intelligence and workspace logic.

Not implemented yet: live trend research, supplier integrations, AI artwork generation, storefront publishing, order fulfillment, customer support automation, marketing execution and financial reconciliation. These are planned in the phased roadmap.

## Run on Termux or Linux
Requires Python 3.10+. No third-party Python packages are required.

    git clone https://github.com/llakshyaa-rgb/Aureon.git
    cd Aureon
    python -m aureon.cli init
    python -m unittest discover -s tests -v
    python -m aureon.cli status\n    python -m aureon.cli workspace\n    python -m aureon.cli run

Open http://127.0.0.1:8787 on the same device. Stop with Ctrl+C.

## Current intelligence tools
The economics module calculates estimated unit costs, fees, profit, margin and break-even advertising cost. It can compare POD and dropshipping offers in the same currency.

The opportunity scorer combines normalized 0-100 signals for demand, trend, margin, competition, shipping and evidence confidence. Higher competition scores mean lower saturation. Each weighted contribution is returned for inspection.

These are decision-support calculations, not sales forecasts. Taxes, duties, returns, foreign exchange and unknown fees must be included as explicit costs when known.

## Local API
- GET /health — health and mode.
- GET /api/overview — job counts.
- GET /api/jobs — recent jobs.\n- GET /api/records?kind=product — workspace records (kind optional).\n- POST /api/records — create a mock-mode workspace record.\n- PATCH /api/records/{id} — change a record status.\n- GET/POST /api/approvals — inspect or request scoped approvals.\n- POST /api/approvals/{id}/decision — decide a pending approval.\n- GET/POST /api/finance — inspect summary or add an actual/estimated ledger entry.
- POST /api/jobs — enqueue a job with JSON such as {"kind":"research.scan","payload":{}}.

The server binds to localhost only. It is not a public API or production storefront.

## Project documentation
- Complete feature inventory: docs/FEATURES.md
- Phased delivery roadmap: docs/ROADMAP.md
- Architecture: docs/ARCHITECTURE.md
- Integration strategy: docs/INTEGRATIONS.md
- Autonomy, approvals and recovery: docs/AUTONOMY.md
- Safety rules: docs/SAFETY.md

## Safety
Mock mode only. No live purchases, supplier orders, ad spend, refunds or public listings. Credentials and local business data must never be committed. Respect marketplace, payment-provider, tax, identity and age requirements.
