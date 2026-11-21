// The agent's own judgment, applied before it asks the chain anything.
// The contract enforces the hard limits; these checks catch what a contract
// cannot see: lookalike names and invoices that try to talk the agent into paying.

const HOMOGLYPHS: [RegExp, string][] = [
  [/0/g, "o"],
  [/[1|!]/g, "l"],
  [/i/g, "l"],
  [/3/g, "e"],
  [/5/g, "s"],
  [/rn/g, "m"],
  [/vv/g, "w"],
  [/[.\-_]/g, ""],
];

/** Collapse characters people confuse, so "acme-c1oud" and "acme-cloud" compare equal. */
export function skeleton(name: string): string {
  let s = name.toLowerCase();
  for (const [re, to] of HOMOGLYPHS) s = s.replace(re, to);
  return s;
}

export function editDistance(a: string, b: string): number {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
  }
  return d[a.length][b.length];
}

/** The trusted name that `name` imitates, if any. An exact match is not an imitation. */
export function lookalikeOf(name: string, trusted: string[]): string | undefined {
  // `trusted` is ordered oldest first. A name the owner trusted later does not
  // clear it of resembling one trusted earlier: the newer one is the suspect.
  const self = trusted.indexOf(name);
  const seniors = self === -1 ? trusted : trusted.slice(0, self);
  const sk = skeleton(name);
  for (const t of seniors) {
    const tk = skeleton(t);
    if (sk === tk) return t;
    if (Math.min(sk.length, tk.length) >= 5 && editDistance(sk, tk) <= 1) return t;
  }
  return undefined;
}

const INJECTION_PATTERNS: [RegExp, string][] = [
  [/ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|limits)/i, "tells the reader to ignore instructions"],
  [/(system|developer) (prompt|message|override)/i, "claims to be a system message"],
  [/\b(you are|act as) (now )?(an?|the) /i, "tries to give the agent a new role"],
  [/\b(override|bypass|disable|raise|increase|lift)\b.{0,40}\b(cap|limit|budget|allowlist|leash|polic)/i, "asks to get around the spending limits"],
  [/\b(approve|pay|sign|send|transfer)\b.{0,30}\b(immediately|right now|urgent|without (review|approval|checking))/i, "pressures for payment without review"],
  [/\b(send|transfer|pay|wire|forward)\b.{0,60}0x[0-9a-fA-F]{40}/i, "names a different wallet to pay"],
  [/\b(do not|don't|never) (tell|notify|alert|escalate|ask)/i, "asks to hide the payment from the owner"],
  [/\b(private key|seed phrase|mnemonic)\b/i, "asks about keys"],
];

/** Why a memo reads like an attempt to instruct the agent. Empty = looks like plain data. */
export function injectionSigns(memo: string): string[] {
  return INJECTION_PATTERNS.filter(([re]) => re.test(memo)).map(([, why]) => why);
}
