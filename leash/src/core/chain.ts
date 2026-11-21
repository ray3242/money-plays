import { defineChain, erc20Abi, type Address } from "viem";
import deployments from "./deployments.json";

export const aevumTestnet = defineChain({
  id: 44005,
  name: "QDay Aevum Testnet",
  nativeCurrency: { name: "Test QDAY", symbol: "tQDAY", decimals: 18 },
  rpcUrls: { default: { http: ["https://rpc-test.qday.info"], webSocket: ["wss://rpc-test.qday.info"] } },
  blockExplorers: { default: { name: "QDay Explorer", url: "https://explorer-test.qday.info" } },
  testnet: true,
});

export const localAnvil = defineChain({
  id: 31337,
  name: "Local Anvil",
  nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
  rpcUrls: { default: { http: ["http://127.0.0.1:8545"] } },
  testnet: true,
});

export type Deployment = { leash: Address; registry: Address; token: Address; deployBlock: number };

export function getDeployment(chainId: number): Deployment | undefined {
  const d = (deployments as Record<string, Deployment>)[String(chainId)];
  return d && d.leash ? d : undefined;
}

export const TOKEN_DECIMALS = 6;
export const TOKEN_SYMBOL = "tUSD8";
export { erc20Abi };

export const CHECK_NAMES = [
  "Ok",
  "LeashNotFound",
  "LeashRevoked",
  "LeashExpired",
  "IntentExpired",
  "BadSignature",
  "InvoiceNotOpen",
  "InvoiceOverdue",
  "WrongPayer",
  "AmountMismatch",
  "PayeeMismatch",
  "PayeeNotAllowed",
  "OverPaymentCap",
  "OverBudget",
  "InsufficientVault",
] as const;

/** Plain-language reason for each on-chain refusal code. */
export const CHECK_TEXT: Record<number, string> = {
  0: "Within the leash",
  1: "This leash does not exist",
  2: "The owner revoked this leash",
  3: "This leash has expired",
  4: "The signed intent is past its deadline",
  5: "The intent was not signed by this leash's agent key",
  6: "The invoice is already paid or cancelled",
  7: "The invoice is past its due date",
  8: "The invoice bills a different payer than the leash owner",
  9: "The amount does not match the invoice",
  10: "The payee name and address do not match the registry",
  11: "The payee is not on this leash's allowlist",
  12: "The amount is over the per-payment cap",
  13: "The amount is over the budget left for this period",
  14: "The owner's vault does not hold enough",
};

export const intentTypes = {
  PaymentIntent: [
    { name: "leashId", type: "uint256" },
    { name: "invoiceId", type: "uint256" },
    { name: "payee", type: "address" },
    { name: "payeeNameHash", type: "bytes32" },
    { name: "amount", type: "uint256" },
    { name: "deadline", type: "uint256" },
  ],
} as const;

export function intentDomain(chainId: number, leash: Address) {
  return { name: "Leash", version: "1", chainId, verifyingContract: leash } as const;
}
