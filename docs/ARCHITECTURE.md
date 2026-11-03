# Architecture

The initial runtime uses Python's standard library and SQLite. This keeps development practical in Termux and avoids adding a database server before the workflows exist.

    Dashboard / local API
             |
      Application services
             |
      Durable job queue ---- Event log
             |
      Domain modules (planned)
      research | scoring | creative | catalog
      channels | fulfillment | marketing | analytics
             |
      Provider adapters (planned)
      trend sources | AI models | POD | dropship
      storefronts | shipping | payment metadata
             |
      SQLite now -> managed database and cloud workers later

## Boundaries

- Domain modules own commerce rules and normalized records.
- Providers translate external APIs into Aureon contracts.
- Jobs are durable units of work and should use idempotency keys.
- Events record important state transitions.
- An approval service will gate consequential external actions.
- The dashboard is a view over services, not the source of business logic.

## Job lifecycle

queued -> running -> succeeded

A running job may fail and return to queued while attempts remain, otherwise it becomes failed. Future workflows may enter needs_approval before side effects. Workers must be idempotent so restarts cannot duplicate orders, listings, or charges.

## Deployment path

1. Phone-local development and mock adapters.
2. Read-only research connectors and product scoring.
3. Design generation and draft catalog creation.
4. Storefront and POD connectors in sandbox or draft-only mode.
5. Approved live workflows with strict spend and action limits.
6. Optional cloud worker for schedules and webhooks; phone remains the control surface.

A cloud move requires backups, schema migrations, encryption, access control, and restore tests.
