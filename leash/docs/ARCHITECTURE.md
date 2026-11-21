# Architecture

## Parts

```
Business wallet ──deposit──▶ Leash.sol (vault per owner)
        │ createLeash / revoke / payAsOwner       ▲ payWithIntent(intent, sig)
        ▼                                         │
   leash rules ◀──previewUnsigned── Agent ──sig──▶ Merchant ──createInvoice──▶ Leash.sol
                                      │                │
                                      └── nameOf ──▶ PayeeRegistry.sol ◀── register
```

### Leash.sol

- **Vault.** `deposit` and `withdraw` move tUSD8 between the owner's wallet and the owner's balance in the contract. Only the owner can withdraw.
- **Leash.** `createLeash(agent, budget, period, perPaymentCap, expiry, allowedPayees)`. `period = 0` makes the budget a lifetime cap; otherwise spending resets each period. An empty payee list means any confirmed payee.
- **Invoice.** A registered payee calls `createInvoice(payer, amount, dueBy, memo)`. The contract stores the payee's name hash at that moment.
- **Payment intent.** EIP-712 struct `PaymentIntent(leashId, invoiceId, payee, payeeNameHash, amount, deadline)` signed by the agent key. `payWithIntent` can be called by anyone.
- **Checks**, in order, each with its own code in the `Check` enum: leash exists, not revoked, not expired; intent deadline; signature; invoice open and not overdue; payer is the leash owner; amount equals the invoice; payee address and name hash match the invoice and the live registry; allowlist; per-payment cap; period budget; vault balance. A failed payment reverts with `Refused(reason)`.
- **Dry run.** `preview(intent, signature)` and `previewUnsigned(intent)` return the `Check` code without sending a transaction. The agent calls it before signing, so it never signs something the contract would refuse, and can tell the owner why.
- **Owner path.** `payAsOwner(invoiceId)` pays an invoice straight from the vault. It does not touch the agent's budget.

### PayeeRegistry.sol

One name per address and one address per name, lowercase `a-z 0-9 . -`, 3 to 32 characters. `confirm(address, name)` answers the confirmation-of-payee question on-chain. Releasing or re-registering a name invalidates signed intents for old invoices, because the name hash no longer matches.

### Agent (`src/core/agent.ts`)

`decide()` is a pure function of chain state plus the agent key:

1. Read the payee's current registered name. If it differs from the invoice's, escalate.
2. Compare the name with payees the business already trusts (its allowlist in the order it was built, then payees it has paid). Names are reduced to a skeleton (`0→o`, `1→l`, `rn→m`, punctuation dropped) and compared by equality and edit distance. A match with a different registration is a lookalike: escalate.
3. Scan the memo for instruction-like text (ignore previous instructions, system override, pay to another address, do not tell the owner, raise the limit). Any hit: escalate.
4. Ask the contract with `previewUnsigned`. Any refusal: escalate with the contract's reason.
5. Otherwise sign.

The agent's screening is deliberately rule-based. An LLM can be added in front of it to read free-form invoices, but the decision to sign never depends on text an invoice author controls, and the hard limits are enforced by the contract whatever the agent does.

## Trust model

| Party | Can | Cannot |
|---|---|---|
| Owner | Deposit, withdraw, create and revoke leashes, edit the allowlist, pay any open invoice billed to it | — |
| Agent key | Authorise payment of an open invoice billed to its owner, inside the leash | Hold or move funds, pay an address with no invoice, exceed cap or budget, pay after revoke or expiry, pay the same invoice twice |
| Merchant | Register a name, bill anyone, cancel own invoices, submit a signed intent | Collect without the agent's or owner's approval, change the amount or the recipient of a signed intent |
| Relayer (anyone) | Submit a valid signed intent and pay its gas | Alter it |

If the agent key leaks, the worst case is bounded by the leash: the remaining budget for the period, at most the cap per payment, only to payees who registered a name and issued an invoice to this owner (and only allowlisted ones if the leash has a list), until the owner revokes.

## Known limits

- The registry is first come, first served and does not verify who is behind a name. In production it would be backed by an issuer or by verified business identity.
- Lookalike and injection screening are heuristics; they reduce risk, the contract limits bound it.
- Invoice memos are public on-chain.
- Works with any standard ERC-20; fee-on-transfer tokens are not supported.
- Not audited.
