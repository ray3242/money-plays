import { keccak256, toHex, type Address, type Hex, type PublicClient, type LocalAccount } from "viem";
import { leashAbi, payeeRegistryAbi } from "./abi";
import { CHECK_NAMES, CHECK_TEXT, intentDomain, intentTypes, type Deployment } from "./chain";
import { injectionSigns, lookalikeOf } from "./screen";

export type Invoice = {
  id: bigint;
  payee: Address;
  payer: Address;
  amount: bigint;
  dueBy: bigint;
  paidAt: bigint;
  status: number; // 1 open, 2 paid, 3 cancelled
  payeeNameHash: Hex;
  paidByLeash: bigint;
  memo: string;
};

export type LeashInfo = {
  id: bigint;
  owner: Address;
  agent: Address;
  expiry: bigint;
  period: bigint;
  periodStart: bigint;
  revoked: boolean;
  allowlistOnly: boolean;
  budget: bigint;
  spentInPeriod: bigint;
  perPaymentCap: bigint;
  totalSpent: bigint;
};

export type PaymentIntent = {
  leashId: bigint;
  invoiceId: bigint;
  payee: Address;
  payeeNameHash: Hex;
  amount: bigint;
  deadline: bigint;
};

export type Decision = {
  invoiceId: bigint;
  leashId: bigint;
  action: "sign" | "escalate";
  /** Short machine-readable cause: "ok", "lookalike", "injection", "name-changed" or a Check name. */
  code: string;
  payeeName: string;
  reasons: string[];
  intent?: PaymentIntent;
  signature?: Hex;
};

export const nameHash = (name: string): Hex => keccak256(toHex(name));

export async function readInvoice(client: PublicClient, d: Deployment, id: bigint): Promise<Invoice> {
  const r = await client.readContract({ address: d.leash, abi: leashAbi, functionName: "getInvoice", args: [id] });
  return { id, ...r, amount: BigInt(r.amount), dueBy: BigInt(r.dueBy), paidAt: BigInt(r.paidAt) };
}

export async function readLeash(client: PublicClient, d: Deployment, id: bigint): Promise<LeashInfo> {
  const r = await client.readContract({ address: d.leash, abi: leashAbi, functionName: "getLeash", args: [id] });
  return {
    id,
    ...r,
    expiry: BigInt(r.expiry),
    period: BigInt(r.period),
    periodStart: BigInt(r.periodStart),
    budget: BigInt(r.budget),
    spentInPeriod: BigInt(r.spentInPeriod),
    perPaymentCap: BigInt(r.perPaymentCap),
    totalSpent: BigInt(r.totalSpent),
  };
}

/** Names the agent treats as known-good: the leash allowlist plus everyone this owner already paid. */
export async function trustedNames(
  client: PublicClient,
  d: Deployment,
  leashId: bigint,
  invoices: Invoice[],
  owner: Address,
): Promise<string[]> {
  const names = new Set<string>(
    await client.readContract({ address: d.leash, abi: leashAbi, functionName: "allowlistOf", args: [leashId] }),
  );
  const paid = invoices.filter((i) => i.status === 2 && i.payer.toLowerCase() === owner.toLowerCase());
  for (const payee of new Set(paid.map((i) => i.payee))) {
    const n = await client.readContract({ address: d.registry, abi: payeeRegistryAbi, functionName: "nameOf", args: [payee] });
    if (n) names.add(n);
  }
  return [...names];
}

/**
 * Decide one open invoice. The agent signs only when its own screening is clean
 * AND the contract's dry run says the payment is inside the leash. Anything else
 * goes to the owner with the reason. Invoice text is treated as data: nothing in
 * a memo can turn an "escalate" into a "sign".
 */
export async function decide(opts: {
  client: PublicClient;
  deployment: Deployment;
  chainId: number;
  leashId: bigint;
  agent: LocalAccount;
  invoice: Invoice;
  trusted: string[];
  /** Seconds a signed intent stays valid. */
  intentTtl?: number;
  now?: number;
}): Promise<Decision> {
  const { client, deployment: d, leashId, invoice: inv } = opts;
  const base = { invoiceId: inv.id, leashId };

  const payeeName = await client.readContract({
    address: d.registry,
    abi: payeeRegistryAbi,
    functionName: "nameOf",
    args: [inv.payee],
  });
  if (!payeeName || nameHash(payeeName) !== inv.payeeNameHash) {
    return {
      ...base,
      action: "escalate",
      code: "name-changed",
      payeeName: payeeName || "(unregistered)",
      reasons: ["The payee's registered name changed or was released after the invoice was issued"],
    };
  }

  const reasons: string[] = [];
  let code = "ok";
  const imitated = lookalikeOf(payeeName, opts.trusted);
  if (imitated) {
    code = "lookalike";
    reasons.push(`"${payeeName}" looks like the trusted payee "${imitated}" but is a different registration`);
  }
  const signs = injectionSigns(inv.memo);
  if (signs.length) {
    if (code === "ok") code = "injection";
    reasons.push(`The memo ${signs.join(" and ")}; memo text is never followed`);
  }

  const now = opts.now ?? Math.floor(Date.now() / 1000);
  const intent: PaymentIntent = {
    leashId,
    invoiceId: inv.id,
    payee: inv.payee,
    payeeNameHash: inv.payeeNameHash,
    amount: inv.amount,
    deadline: BigInt(now + (opts.intentTtl ?? 3600)),
  };
  const check = await client.readContract({
    address: d.leash,
    abi: leashAbi,
    functionName: "previewUnsigned",
    args: [intent],
  });
  if (check !== 0) {
    if (code === "ok") code = CHECK_NAMES[check];
    reasons.push(CHECK_TEXT[check]);
  }
  if (code !== "ok") return { ...base, action: "escalate", code, payeeName, reasons };

  const signature = await opts.agent.signTypedData({
    domain: intentDomain(opts.chainId, d.leash),
    types: intentTypes,
    primaryType: "PaymentIntent",
    message: intent,
  });
  return {
    ...base,
    action: "sign",
    code,
    payeeName,
    reasons: [`Confirmed payee "${payeeName}", amount inside the cap and budget`],
    intent,
    signature,
  };
}
