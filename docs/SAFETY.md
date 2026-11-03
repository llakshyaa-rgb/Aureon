# Safety rules

Aureon may eventually interact with money, marketplaces, suppliers, and customers. These rules are architectural requirements.

## Defaults

- New installations start in mock mode.
- No live supplier orders, ad spend, refunds, or public listing publication in the foundation milestone.
- Bind the local server to loopback. Do not expose it through a tunnel or router port-forward.
- Live mode requires explicit configuration and separate testing.

## Approval gates

Require a human approval record before paying a supplier, placing a fulfillment order, spending on ads or subscriptions, publishing a listing, issuing refunds or compensation, changing payout/tax/identity/bank details, or sending customer messages that make financial or legal commitments.

Approvals should be scoped to one action, include a maximum amount where relevant, expire, and be auditable.

## Credentials

Never commit API keys, access tokens, cookies, OAuth refresh tokens, bank information, or customer personal data. Keep environment files, local databases, credential files, logs, and exports out of Git. Use narrow API scopes and never print secrets in logs or health endpoints.

## Evidence

Preserve source URL, collection time, region, and extraction method for market claims. Mark AI-generated demand, pricing, competitor, and margin statements as hypotheses until verified. Check trademarks, copyright, platform policies, product restrictions, and supplier terms before publishing. Never represent estimated margins as guaranteed profit.

## Eligibility

Respect each marketplace, payment provider, and jurisdiction's eligibility, identity verification, tax, and age requirements. Never falsify identity or route payouts through an account without the account holder's informed authorization.
