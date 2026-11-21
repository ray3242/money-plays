import test from "node:test";
import assert from "node:assert/strict";
import { rank, usedCounts } from "../triage.mjs";

const now = Date.parse("2026-11-26T00:00:00Z");
const day = 24 * 3600e3;
const markets = {
  markets: [
    { marketAddress: "0xA", question: "Will the November CPI print at or above 4.00%?", odds: { yes: 0.5 }, evidenceCutoff: new Date(now + 5 * day).toISOString() },
    { marketAddress: "0xB", question: "Will team X win?", odds: { yes: 0.97 }, evidenceCutoff: new Date(now + 5 * day).toISOString() },
    { marketAddress: "0xC", question: "Closed to evidence", odds: { yes: 0.5 }, evidenceCutoff: new Date(now - 1000).toISOString() },
    { address: "0xD", title: "Different field names", probability: 45, closeTime: (now + 3 * day) / 1000 },
    { marketAddress: "0xE", question: "Unknown everything" },
  ],
};

test("open, undecided, record-based markets rank first; dead ones last", () => {
  const r = rank(markets, now);
  assert.equal(r[0].address, "0xA");
  assert.equal(r.at(-1).score, 0);
  assert.equal(r.find((m) => m.address === "0xC").score, 0);
  assert.ok(r.find((m) => m.address === "0xB").score < r.find((m) => m.address === "0xD").score);
  assert.ok(r.find((m) => m.address === "0xE").score > 0);
});

test("a market with 3 submissions used drops to zero", () => {
  const log = ['{"marketAddress":"0xa","id":"s1"}', '{"marketAddress":"0xa","claim":"x"}', '{"marketAddress":"0xA","id":"s2"}', '{"marketAddress":"0xa","id":"s3"}', '{"marketAddress":"0xa","id":null,"status":"no_answer"}', "garbage"].join("\n");
  const used = usedCounts(log);
  assert.equal(used["0xa"], 3);
  assert.equal(rank(markets, now, used).find((m) => m.address === "0xA").score, 0);
});
