# Safety Rules

Aureon may eventually interact with money, marketplaces, suppliers and customers. These are architectural requirements.

## Defaults
- New installations start in local mode with no provider credentials and no automatic external actions.
- Research connectors are read-only by default.
- Listings are drafts by default.
- No live supplier orders, ad spend, refunds, subscriptions or public publishing without explicit authorization.
- Bind the local server to loopback; do not expose it through a tunnel or router port-forward.
- A roadmap entry does not enable a live integration.

## Approval gates
Require human approval before paying a supplier, placing a fulfillment order, spending on ads or subscriptions, publishing a listing, issuing refunds or compensation, changing payout/tax/identity/bank details, or sending customer messages that make financial or legal commitments.

Approvals must be scoped to one action, target, account and amount; expire; be single-use; and be auditable. A changed amount or destination requires new approval.

## Credentials and personal data
Never commit API keys, access tokens, cookies, OAuth refresh tokens, bank information or customer personal data. Keep environment files, local databases, credential files, logs and exports out of Git. Use narrow API scopes and never print secrets in logs or health endpoints.

## Evidence and creative rights
Preserve source URL, collection time, region and extraction method for market claims. Mark AI-generated demand, pricing, competitor and margin statements as hypotheses until verified. Check trademarks, copyright, platform policies, product restrictions and supplier terms before publishing. Do not copy competitors' artwork or misrepresent products.

## Financial accuracy
Never represent estimated margins as guaranteed profit. Distinguish gross revenue, gross profit, contribution profit and net profit. Account for supplier cash-flow timing and payout delays.

## Eligibility and customer safety
Respect marketplace, payment-provider, jurisdiction, identity, tax and age requirements. Never falsify identity or route payouts through an account without informed authorization. Escalate safety issues, legal threats, chargebacks and uncertain refund disputes. Do not make unverified delivery promises or financial/legal commitments.
