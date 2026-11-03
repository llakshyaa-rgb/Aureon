# Integration Strategy

Aureon uses provider adapters behind stable internal contracts. Integrations are optional; the core app must run without API credentials.

| Group | Initial candidates | Responsibility |
|---|---|---|
| Trends and demand | Google Trends and compliant public sources | Search interest, seasonality, regional signals |
| Social research | Official APIs or approved providers | Trend and content signals within platform terms |
| Dropshipping | CJdropshipping and other vetted suppliers | Catalog, stock, quote, shipping, order status |
| POD | Printify, Printful, Gelato | Catalog, print areas, production quote, fulfillment |
| Storefront | Shopify, WooCommerce | Draft listings, products, orders, inventory |
| AI models | Pluggable text and image providers | Research synthesis, copy, design assistance |
| Finance | Store/payment reporting APIs | Transaction and payout metadata, not bank passwords |
| Analytics | Store, campaign and traffic APIs | Orders, conversion, attribution and performance |

## Adapter contract
Every adapter should expose provider identity and capabilities; credential validation without logging secrets; rate-limit handling and bounded retries; typed normalized results and original provider IDs; source URL, retrieval time, region and currency; sandbox/read-only/draft/live capability flags; idempotency for writes where available; structured retryable and permanent errors.

## Provider selection rules
1. Verify current API availability, country support, terms, fees and eligibility at implementation time.
2. Prefer official APIs and documented webhooks.
3. Do not scrape or automate sites in ways that violate terms.
4. Keep provider-specific fields inside adapters.
5. Never assume a marketplace is also a fulfillment provider.
6. Never commit tokens, refresh tokens, cookies or customer data.
7. Require sandbox, failure and permission-scope tests before live use.

Provider availability and fees change. Respect account ownership, identity, tax, age, payout and local-law requirements. Never falsify identity or use another person's account without informed authorization.
