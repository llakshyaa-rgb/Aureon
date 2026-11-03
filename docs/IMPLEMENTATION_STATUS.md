# Implementation Status

This status is deliberately conservative. "In progress" means useful local workflows exist; it does not mean live providers are connected.

## Six expanded capability areas in this milestone

1. **Opportunity intelligence:** evidence URL and timestamp validation, analyst-supplied signals, weighted score and saved opportunity record.
2. **Supplier research:** supplier profiles, timestamped manual quotes and same-currency/destination landed-cost comparisons. Quotes are unverified until independently confirmed.
3. **Order operations:** order simulation, approval request, matching-approval check before recording supplier submission, and tracking/status updates. No supplier is contacted and no order is actually placed.
4. **Campaign analytics:** recorded campaign observations and CTR, conversion rate, cost/order, ROAS and revenue-minus-ad-spend calculations. ROAS is not profit.
5. **Scheduling:** persistent scheduled jobs and a manual tick that enqueues due jobs. The scheduler does not run itself in the background.
6. **Worker integration:** mock processors for opportunity assessment and campaign calculations, alongside the previous design/listing/support/marketing/economics processors.

## Existing local capabilities

- Python/SQLite runtime, local-only dashboard and JSON API.
- Durable queue with idempotency, bounded retries and interrupted-job recovery.
- Unit economics and POD/dropshipping comparison.
- Structured design briefs and listing/marketing/support drafts.
- Workspace records, approval records and currency-separated actual/estimated ledger.

## Still not implemented

- Live trend/search/social scraping or APIs.
- Live supplier catalogs, availability, verified shipping quotes or supplier ordering.
- AI image generation, mockups or print-ready asset validation.
- Shopify/WooCommerce/marketplace publishing or inventory sync.
- Actual fulfillment-provider and carrier integrations.
- Connected customer inbox or autonomous replies.
- Social publishing, ad buying or attribution integrations.
- Payment/payout reconciliation, taxes, FX feeds and cash-flow forecasting.
- Multi-agent planning/delegation, secure remote/cloud worker, unattended scheduler daemon.
- Full multi-page interactive command center and natural-language command interpreter.

## Verification

Automated tests have been added, including tests for the expanded workflows, but this repository update has not been executed in the target Termux environment. Do not treat it as verified until this passes:

    python -m unittest discover -s tests -v

## Commands

    python -m aureon.cli init
    python -m aureon.cli tick
    python -m aureon.cli work
    python -m aureon.cli status
    python -m aureon.cli run

The API binds to localhost. Mock mode does not make purchases, publish listings, send messages or spend money.
