# Aureon — Complete Product Roadmap

Aureon is intended to become a global AI-operated commerce workspace spanning print-on-demand (POD) and conventional dropshipping. This is the complete agreed scope, not a claim that every feature is already implemented.

## Product objective
A user gives Aureon a business objective. It researches markets, finds and evaluates products, chooses a suitable model, creates product assets and listings, prepares publishing, helps operate orders and support, measures actual economics, and improves future decisions from recorded outcomes. It must perform real trackable work, not merely return chat recommendations.

## Product principles
1. Evidence before confidence: retain source, region, collection time and method.
2. Profit before popularity: include landed costs, fees, returns, taxes, duties, FX and advertising where known.
3. POD and dropshipping are peers; compare both rather than forcing one.
4. Draft-first and approval-gated for consequential actions.
5. Recoverable by design: persistent state, idempotency, bounded retries and event logs.
6. Phone-first development in Termux; cloud workers only when justified.
7. Provider independence: business logic must not depend on one supplier, model or store.
8. Never invent demand, shipping, ratings, revenue or margins.

## Delivery phases and exit criteria

| Phase | Scope | Exit criteria |
|---|---|---|
| 1. Foundation | Local runtime, SQLite, queue, recovery, API, tests | Restart-safe jobs; tests pass; no secrets committed |
| 2. Discovery | Trend sources, evidence store, competitor research | Every opportunity has traceable source, region and timestamp |
| 3. Economics | Supplier catalog, shipping quotes, POD/drop comparison | Comparable landed-cost breakdown and explainable recommendation |
| 4. Creative | Artwork workflows, validation, mockups, collections | Provider-ready assets with provenance and review state |
| 5. Catalog and publishing | Listings, SEO, store/provider adapters | Draft creation and reconciliation in sandbox/test mode |
| 6. Operations | Orders, supplier routing, tracking, support | Idempotent simulated order lifecycle and approval gates |
| 7. Marketing | Content and campaign analytics | Draft content plus measurable experiment records |
| 8. Finance | Payout, cost, profit and cash-flow ledger | Reconciled reports distinguish actual from estimated figures |
| 9. Autonomy | Multi-agent orchestration, schedules, memory | Recoverable end-to-end workflows with audit trails |
| 10. Cloud expansion | Hosted workers, webhooks, backups, access control | Secure deployment, restore test, monitoring and cost controls |

## Operating modes
- **Mock:** synthetic data and simulated side effects only.
- **Research:** read-only external data gathering.
- **Draft:** create local or store drafts without publishing.
- **Live with approvals:** consequential actions require scoped approval.
- **Bounded autonomy:** only explicitly allow-listed actions under configured limits.

A roadmap entry does not enable live mode. Each live connector requires separate implementation, provider review, security testing and configuration.

## Constraints
No guaranteed sales or profit; no bypassing marketplace rules, APIs, identity checks or age requirements; no fake reviews, deceptive scarcity, spam, copied artwork or counterfeit goods; no uncontrolled ad spend, supplier charges, refunds or customer commitments. No GitHub Actions dependency. Avoid paid infrastructure until a measured need justifies it.
