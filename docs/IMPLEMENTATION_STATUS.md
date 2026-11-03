# Implementation Status

This status describes code that exists locally in the repository. "In progress" means useful local workflows exist; it does not mean live providers are connected. Automated tests are committed but have not yet been run in the target Termux environment.

## Six expanded capability areas

1. **Opportunity intelligence**
   - Evidence URLs must be public HTTP(S) links with timezone-aware collection timestamps; duplicate URLs are collapsed.
   - Demand, trend, margin, competition, shipping and confidence inputs are range-checked and scored with visible weights.
   - Saves evidence, normalized inputs, score, region and business-model hint in the workspace.
   - Signals are entered by the operator; no live trend feed is connected.

2. **Supplier research**
   - Supplier profiles and manually entered quotes with timestamp, destination, currency, costs and notes.
   - Comparisons only include matching product type, destination and currency; results include landed cost and quote-age freshness labels.
   - Quotes remain explicitly unverified; no supplier website is scraped and no stock or shipping promise is inferred.

3. **Order operations**
   - Creates local simulated orders with optional validated supplier references.
   - Approval is tied to the exact order, amount and currency; a pending approval cannot be duplicated.
   - Submission record consumes the one-time approval, preventing replay; fulfillment updates follow an explicit status path.
   - This records a simulated submission reference only. It does not contact or place an order with a supplier.

4. **Campaign analytics**
   - Stores timestamped campaign observations in one currency per campaign.
   - Validates count relationships and computes CTR, conversion rate, cost per order, ROAS and revenue minus ad spend.
   - ROAS and revenue-minus-ad-spend are not profit; other costs remain outside this campaign metric calculation.

5. **Scheduling**
   - Stores timezone-aware scheduled jobs with payload and idempotency key.
   - Conflicting reuse of an idempotency key is rejected; due-job enqueue and schedule-state update are atomic.
   - Run `python -m aureon.cli tick` to enqueue due jobs, then `python -m aureon.cli work` to process them. No background daemon is installed.

6. **Worker integration**
   - Mock processors cover design briefs, listing drafts, support triage, marketing drafts, economics, opportunity assessment, campaign metrics and product records.
   - Draft-producing jobs persist workspace records; errors are recorded as failed jobs.
   - No external side effects are enabled.

## Shared local foundation

- Python/SQLite persistence, event history, durable queue, idempotency, bounded retries and interrupted-job recovery.
- Localhost-only dashboard and JSON API for records, jobs, approvals, finance, suppliers, orders, campaign observations and schedules.
- Unit economics and POD/dropshipping comparison.
- Actual-versus-estimated finance ledger, kept separate by currency.
- Explicit record state transitions and input validation.

## Not implemented / not claimed complete

- Live search/social trend collection, automated market-size research or competitor scraping.
- Supplier catalogs, verified quotes, inventory checks, supplier communication or real order submission.
- AI image generation, mockups, asset management or print-ready QA.
- Shopify/WooCommerce/marketplace publishing and inventory synchronization.
- Actual fulfillment-provider/carrier integrations or customer shipment notifications.
- Connected customer inbox, autonomous customer replies, social publishing or ad buying.
- Bank/payment-provider reconciliation, taxes, live FX, actual refund execution or predictive cash-flow forecasting.
- Dependency-aware agent orchestration, remote/cloud execution, background scheduler daemon, or unrestricted natural-language command execution.

## Verification still required

The repository now contains unit tests for core queue/economics/scoring, workspace/approvals/finance, worker processing and the expanded workflows. They have **not** been executed here: the execution environment could not reach GitHub to clone the repository. Run the following in Termux after pulling the commits:

    python -m unittest discover -s tests -v

Do not treat the milestone as verified until the full suite passes.

## Commands

    python -m aureon.cli init
    python -m aureon.cli tick
    python -m aureon.cli work
    python -m aureon.cli status
    python -m aureon.cli run

The server binds to localhost. Mock mode does not make purchases, publish listings, send messages or spend money.


## Last six local workflow domains

These six domains now have local/mock service modules and HTTP API surfaces. The status `local_mock_complete` means the local workflow is implemented; it does not mean live commerce integrations or production readiness.

- **Order and fulfillment:** simulated orders, amount/currency-bound approvals, one-time submission records, tracking transitions and refund-review approvals. No supplier is contacted and no refund is issued.
- **Customer support:** persistent ticket intake, urgency classification, internal notes, response drafts and queue summaries. Responses are never sent automatically; inbox imports are not connected.
- **Marketing:** channel-specific campaign drafts, budget estimates and explicit publication/ad-spend approval requests. No campaign is published and no ad account is charged.
- **Finance:** actual/estimated currency-separated ledger, manual reconciliation and scenario cash-flow projections. No bank, payout, tax or FX provider is connected.
- **Agent runtime:** allowlisted task plans enqueue durable jobs with idempotency; runtime exposes queue and run status. Workers are manually invoked; plans are supervised and cannot execute shell commands or arbitrary code. Dependency references are validated but dependency gating is not yet enforced by the worker.
- **Command center:** localhost dashboard panels, read-only consolidated snapshot, API routes and a narrow command interpreter. It does not autonomously execute commands.

New API surfaces include /api/support, /api/marketing/campaigns, /api/finance/dashboard, /api/finance/reconcile, /api/finance/forecast, /api/agents, /api/agents/plans, /api/command-center and /api/commands/interpret. Order refund review is available at /api/orders/{id}/refund-review.

## Last-six verification

`tests/test_last_six.py` covers the new services. The full suite, HTTP smoke tests and target-device Termux run still need to be executed before these can be marked verified. A committed test is not proof that it passes.
