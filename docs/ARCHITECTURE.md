# Architecture

Aureon is a local-first, provider-independent commerce operating system. Python standard library and SQLite keep the initial runtime practical on Android Termux.

    Phone dashboard / local API
               |
       Application services
               |
    Agent orchestrator + scheduler
               |
       Durable job queue ---- Event/audit log
               |
    Domain services
    intelligence | research | economics | creative
    catalog | channels | fulfillment | support
    marketing | finance | analytics | approvals
               |
       Provider adapter contracts
    trends | AI | dropship | POD | storefront
    payments metadata | social | analytics
               |
       SQLite local -> managed DB/cloud workers later

## Domain boundaries
- Domain services own business rules and normalized records.
- Provider adapters translate external APIs to internal contracts.
- Agents coordinate services but cannot bypass approvals.
- Jobs are durable and idempotent; events explain state changes.
- Approval service gates consequential external actions.
- Dashboard is a view and command surface, not the source of business truth.
- Credentials are isolated from domain data and never returned by APIs.

## Domain responsibilities
| Domain | Responsibility |
|---|---|
| intelligence | Trends, market signals, competitors, opportunity scoring |
| research | Products, suppliers, shipping quotes, evidence |
| economics | Costs, pricing, margin, channel comparison |
| creative | Design briefs, artwork, mockups, validation |
| catalog | Product records, variants, SEO, listing drafts |
| channels | Storefront and marketplace publishing adapters |
| fulfillment | Orders, supplier routing, tracking, exceptions |
| support | Customer inquiry triage and response drafts |
| marketing | Content, campaigns, experiments and attribution |
| finance | Ledger, payouts, fees, cash flow and profit reporting |
| agents | Orchestration, memory, scheduling, delegation |
| approvals | Scoped authorization for consequential actions |
| analytics | Dashboards, metrics and performance history |

## Data and job lifecycle
Jobs move through queued -> running -> succeeded. A running job may return to queued while retry attempts remain, otherwise it becomes failed. Future workflows may enter needs_approval before external side effects. Workers must reconcile uncertain outcomes before retrying purchases, publishing or refunds.

Evidence records include source URL, provider, region, collection time, currency where relevant, extraction method and confidence/freshness. Financial records distinguish actual, estimated and forecast values.

## Deployment path
1. Phone-local development and mock adapters.
2. Read-only research connectors.
3. Design generation and draft catalog creation.
4. Storefront and POD connectors in sandbox or draft-only mode.
5. Approved live workflows with strict limits and audit trails.
6. Optional cloud workers for schedules and webhooks.

Cloud deployment requires backups, schema migrations, encryption, access control, monitoring, restore tests and cost limits.
