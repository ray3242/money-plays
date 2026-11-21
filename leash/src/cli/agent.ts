// Headless Leash agent. Watches invoices billed to one leash's owner, signs a
// payment intent for each one that passes its screening and the on-chain dry
// run, and (if RELAYER_KEY is set) submits it. The agent key itself never holds
// funds or gas.
//
//   AGENT_KEY=0x…  LEASH_ID=1  [RELAYER_KEY=0x…]  [RPC_URL=…]  [ONCE=1]  npm run agent
import { createPublicClient, createWalletClient, formatUnits, http, type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { leashAbi } from "../core/abi";
import { decide, readInvoice, readLeash, trustedNames, type Decision, type Invoice } from "../core/agent";
import { aevumTestnet, getDeployment, localAnvil, TOKEN_DECIMALS, TOKEN_SYMBOL, type Deployment } from "../core/chain";

function env(name: string, required = true): string {
  const v = process.env[name];
  if (!v && required) {
    console.error(`Missing ${name}. See the header of src/cli/agent.ts.`);
    process.exit(1);
  }
  return v ?? "";
}

const rpcUrl = process.env.RPC_URL ?? aevumTestnet.rpcUrls.default.http[0];
const client = createPublicClient({ transport: http(rpcUrl) });
const chainId = await client.getChainId();
const chain = chainId === localAnvil.id ? { ...localAnvil, rpcUrls: { default: { http: [rpcUrl] } } } : aevumTestnet;

const deployment: Deployment | undefined = process.env.LEASH_ADDRESS
  ? {
      leash: env("LEASH_ADDRESS") as Address,
      registry: env("REGISTRY_ADDRESS") as Address,
      token: env("TOKEN_ADDRESS") as Address,
      deployBlock: 0,
    }
  : getDeployment(chainId);
if (!deployment) {
  console.error(`No Leash deployment known for chain ${chainId}. Set LEASH_ADDRESS, REGISTRY_ADDRESS and TOKEN_ADDRESS.`);
  process.exit(1);
}
const d = deployment;

const agent = privateKeyToAccount(env("AGENT_KEY") as Hex);
const leashId = BigInt(env("LEASH_ID"));
const relayer = process.env.RELAYER_KEY
  ? createWalletClient({ account: privateKeyToAccount(process.env.RELAYER_KEY as Hex), chain, transport: http(rpcUrl) })
  : undefined;
const once = !!process.env.ONCE;
const pollMs = Number(process.env.POLL_MS ?? 5000);

const fmt = (v: bigint) => `${formatUnits(v, TOKEN_DECIMALS)} ${TOKEN_SYMBOL}`;
const log = (o: Record<string, unknown>) =>
  console.log(JSON.stringify({ t: new Date().toISOString(), ...o }, (_, v) => (typeof v === "bigint" ? v.toString() : v)));

/** Invoices already escalated, so the owner is told once, not on every poll. */
const escalated = new Map<bigint, string>();

async function submit(dec: Decision): Promise<void> {
  if (!relayer || !dec.intent || !dec.signature) return;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const hash = await relayer.writeContract({
        address: d.leash,
        abi: leashAbi,
        functionName: "payWithIntent",
        args: [dec.intent, dec.signature],
      });
      const receipt = await client.waitForTransactionReceipt({ hash });
      if (receipt.status !== "success") throw new Error(`transaction ${hash} reverted`);
      log({ event: "paid", invoice: dec.invoiceId, tx: hash });
      return;
    } catch (e) {
      // Paying is idempotent on-chain: if an earlier attempt landed, the invoice is no longer open.
      const inv = await readInvoice(client, d, dec.invoiceId);
      if (inv.status !== 1) {
        log({ event: "already-settled", invoice: dec.invoiceId });
        return;
      }
      log({ event: "submit-retry", invoice: dec.invoiceId, attempt, error: (e as Error).message.split("\n")[0] });
      await new Promise((r) => setTimeout(r, 1000 * attempt));
    }
  }
  log({ event: "submit-failed", invoice: dec.invoiceId });
}

async function tick(): Promise<void> {
  const leash = await readLeash(client, d, leashId);
  if (leash.agent.toLowerCase() !== agent.address.toLowerCase()) {
    throw new Error(`AGENT_KEY is ${agent.address} but leash ${leashId} is held by ${leash.agent}`);
  }
  const ids = await client.readContract({ address: d.leash, abi: leashAbi, functionName: "invoicesFor", args: [leash.owner] });
  const invoices: Invoice[] = await Promise.all(ids.map((id) => readInvoice(client, d, id)));
  const trusted = await trustedNames(client, d, leashId, invoices, leash.owner);
  const block = await client.getBlock();

  for (const invoice of invoices.filter((i) => i.status === 1)) {
    const dec = await decide({
      client,
      deployment: d,
      chainId,
      leashId,
      agent,
      invoice,
      trusted,
      now: Number(block.timestamp),
    });
    if (dec.action === "escalate") {
      if (escalated.get(invoice.id) === dec.code) continue;
      escalated.set(invoice.id, dec.code);
      log({ event: "escalated", invoice: invoice.id, payee: dec.payeeName, amount: fmt(invoice.amount), code: dec.code, reasons: dec.reasons });
      continue;
    }
    log({
      event: "signed",
      invoice: invoice.id,
      payee: dec.payeeName,
      amount: fmt(invoice.amount),
      ...(relayer ? {} : { intent: dec.intent, signature: dec.signature }),
    });
    await submit(dec);
    // A name authorized in this poll counts as trusted for the invoices that follow it.
    if (!trusted.includes(dec.payeeName)) trusted.push(dec.payeeName);
  }
}

log({ event: "start", chainId, leash: d.leash, leashId, agent: agent.address, relayer: relayer?.account.address ?? null });
for (;;) {
  try {
    await tick();
  } catch (e) {
    log({ event: "error", error: (e as Error).message.split("\n")[0] });
    if (once) process.exit(1);
  }
  if (once) break;
  await new Promise((r) => setTimeout(r, pollMs));
}
