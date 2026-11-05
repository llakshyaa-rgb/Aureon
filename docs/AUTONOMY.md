# Autonomy, Approvals and Recovery

Aureon should automate research and preparation aggressively while protecting money, customers and external accounts.

## Action risk classes
| Class | Examples | Default |
|---|---|---|
| Read-only | Trend research, catalog reads, analytics sync | May run automatically within limits |
| Internal/reversible | Score opportunity, prepare design brief, draft listing | May run automatically and be logged |
| External non-financial | Save a draft listing, sync metadata | Approval or explicit provider policy |
| Financial/irreversible | Supplier purchase, ad spend, subscription, refund | Explicit scoped approval |
| Sensitive account | Payout, bank, tax, identity, permissions | Human-only; never agent-controlled |

## Approval record
An approval identifies the exact action, target, amount and currency where relevant, and is single-use. Pending approvals expire 24 hours after request. Changed amounts or destinations require a new approval.

## Reliability rules
- Persist job state before external side effects.
- Use stable job IDs and idempotency keys.
- Use provider idempotency or reconcile state before retrying a write.
- Retry transient worker errors only, with a bounded attempt count. The local background worker polls between attempts; the synchronous drain command may retry immediately.
- Treat a timeout after a write as ambiguous; reconcile before repeating.
- Record every state transition and external provider reference.
- Recover interrupted jobs at startup; fail interrupted multi-step agent plans closed rather than replaying completed steps.
- Escalate repeated or ambiguous failures rather than looping.

## Autonomy levels
1. Mock: simulated effects only.
2. Research: external read-only calls.
3. Draft: prepare content and listings without publication.
4. Approval-gated live: each consequential action reviewed.
5. Bounded autonomy: individually allow-listed actions under explicit spend, quantity and frequency limits.

Enabling one level must not silently enable a higher level. The dashboard must show current permissions and pending approvals.
