# Aureon Complete Feature Inventory

This is the canonical feature checklist. The Python registry in aureon/features.py is its machine-readable companion.

## Status meanings
- **foundation** — supporting infrastructure or an initial calculation exists; the entire domain is not complete.
- **planned** — committed product scope, not yet operational.
- Future statuses: **in_progress**, **testing**, and **complete**, assigned only after implementation and verification.

## 1. Global Opportunity Intelligence
Worldwide product, niche and micro-niche discovery; search trends, social signals, seasonality and regional interest; competitor listings, pricing, positioning and saturation; underserved-market discovery; historical trend tracking; momentum detection; explainable ranking with source evidence, confidence and rejection reasons.

## 2. Product and Supplier Research
Normalized supplier and POD catalog search; price, availability, quality, ratings and reliability comparison; destination-specific shipping and delivery quotes; landed cost; quote freshness; supplier history; restricted-product and policy checks.

## 3. Profitability and Business Model Selection
Product, shipping, packaging, platform, payment, advertising, return, tax, duty and FX cost inputs; contribution profit, margin and break-even ad cost; POD versus dropshipping comparison; price recommendations and sensitivity analysis; cash required to fulfill an order; reject, investigate or recommend with evidence.

## 4. Creative Studio
Original apparel and product artwork; collections and variations; mockups and promotional assets; print-ready validation for dimensions, transparency, safe areas and provider requirements; brand identities and logos; trademark/copyright risk screening with human review; design-to-product matching.

## 5. Product Catalog and Listing SEO
Normalized products, variants, assets, source evidence and costs; SEO titles, descriptions, tags, categories and alt text; channel-specific listing generation; localization; pricing suggestions; duplicate and stale-data detection; draft review.

## 6. Stores and Marketplace Publishing
Shopify and WooCommerce storefront adapters; Printify, Printful and Gelato POD adapters; other marketplaces only where APIs and terms permit; draft publishing, variant and inventory sync, listing reconciliation; sandbox testing before live publication. A POD supplier is not automatically a marketplace.

## 7. Order and Fulfillment Operations
Order intake and validation; supplier routing; purchase-order preparation; approval-gated supplier ordering and funds checks; production, dispatch, delivery and tracking sync; failed, delayed, duplicate and partial-order detection; controlled cancellation and refund workflows.

## 8. Customer Support
Inquiry classification and order context; product, shipping and delivery response drafts; complaint, escalation and chargeback-risk detection; conversation history; policy-aware support; human approval for refunds and financial/legal commitments.

## 9. Marketing and Growth
Social posts, ad concepts, product creative, email drafts and short-video briefs; TikTok, Instagram, Pinterest and permitted channel workflows; competitor positioning research; campaign spend, engagement, clicks, conversion and attributed-sales analysis; experiments and approval-gated budgets.

## 10. Financial Intelligence
Sales, refunds, fees, supplier charges, shipping, taxes, advertising and payouts; product-, channel-, country- and period-level profitability; supplier cash-flow timing; payout tracking without bank credential storage; multi-currency reporting with FX timestamps; daily, weekly and monthly reports. Actual, estimated and forecast values stay distinct.

## 11. Autonomous Agent Runtime
Durable jobs, schedules, event history and long-term business memory; research, creative, catalog, operations, support, marketing and finance agents; task delegation and prioritization; bounded retries, crash recovery and idempotency; decision explanations, approvals and outcomes; daily summaries; optional cloud workers and webhooks.

## 12. Aureon Command Center
Business overview; discovery, research, supplier comparison and economics; creative studio and asset library; products, stores, listings, orders and fulfillment; marketing, finance and analytics; agent activity, failures, approvals and audit log; memory, integrations, permissions and spend limits; natural-language commands that launch trackable workflows.

See ROADMAP.md for delivery order and exit criteria.
