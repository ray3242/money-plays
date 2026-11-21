# DoraHacks submission text (QDay Aevum Builder Challenge #1)

**Project name:** Leash

**One-liner:** Give an AI agent a budget, not your wallet: on-chain spending limits, confirmed payees and gasless signed stablecoin payments on Aevum.

**Tracks:** Agentic Payments; AI Fraud Prevention; Confirmation of Payee

**Links**
- Repository: https://github.com/ray3242/money-plays/tree/main/leash
- Live demo: https://ray3242.github.io/leash/
- Demo video: VIDEO_URL
- Leash contract: EXPLORER_LEASH
- PayeeRegistry contract: EXPLORER_REGISTRY

## Description (paste into the BUIDL description)

### Problem
Businesses want AI agents to pay routine invoices, but today that means giving the agent a funded wallet or an unlimited token approval. One prompt injection, one lookalike vendor or one leaked key can drain the account. Traditional payment rails have spending limits, dual approval and payee name checks. Stablecoin rails do not have them by default.

### Solution
Leash keeps the business's stablecoins in its own on-chain vault and gives the agent only a leash:

- a budget per period and a cap per payment,
- an expiry date and an optional list of allowed payees,
- one-click revoke that kills every outstanding signature in the same block.

The agent holds no funds and no gas. It reads an invoice, checks it, and signs an EIP-712 payment intent. The merchant (or any relayer) submits the signature; the contract pays from the vault only if every rule holds, and otherwise reverts with the exact reason.

Payments go to names, not hex strings. Merchants register a name in an on-chain PayeeRegistry, and the agent's signature binds both the name and the address, so a changed or released name makes the payment fail (confirmation of payee).

Before signing, the agent also screens for fraud: names that imitate a payee the business already trusts (`acme-c1oud` vs `acme-cloud`), and invoice memos that try to give it instructions. Those are escalated to the owner with the reason in plain words. The owner can pay an escalated invoice directly, which does not use the agent's budget.

### Complete stablecoin payment flow on Aevum Testnet
1. The business deposits tUSD8 into the Leash vault and creates a leash for its agent.
2. A merchant registers `acme-cloud` in the PayeeRegistry and issues an invoice.
3. The agent dry-runs the payment against the contract, screens payee and memo, and signs.
4. The merchant submits the signed intent; tUSD8 moves from the vault to the merchant; the budget is reduced.
5. An over-cap invoice, a prompt-injection memo, a lookalike payee and a redirect scam are each refused and escalated.

Transactions from the live deployment: TX_LINKS

### Architecture
Two Solidity contracts (`Leash.sol`, `PayeeRegistry.sol`, OpenZeppelin 5.1), a TypeScript decision core shared by a headless agent CLI and a no-framework web app (viem, Vite). Details: `docs/ARCHITECTURE.md`.

### Testing
23 Foundry tests including a fuzz test proving the budget can never be exceeded; unit tests for the screening rules; a scripted end-to-end run of the headless agent on a local chain; and a Playwright walkthrough that drives the web app through the whole story (it recorded the demo video).

### What is next
Issuer-backed payee names, multi-token vaults, co-signer thresholds for large payments, and an x402-style HTTP adapter so any agent framework can pay through a leash.

## Demo Day
If shortlisted (top 5), a live presentation is required on 15 Dec 2026 06:00 UTC (14 Dec, 11:00 pm Edmonton). Script: run the live demo through the five steps above, about 4 minutes.
