#!/usr/bin/env node
// Ranks Delphi competition markets by how worth researching they are, following
// the official guide (reference/evidence.md): odds between 20% and 80%, enough
// time before the evidence cutoff, and not already used up by this account.
//
//   node triage.mjs                      # fetches https://competition.delphi.fyi/markets.json
//   node triage.mjs markets.json         # or reads a saved copy
//   node triage.mjs --used ../gensyn-delphi-skills/evidence-log.jsonl
//
// The market list's field names are not published before the competition opens,
// so every field is looked up under several likely names. Unknown values lower
// confidence, never crash the run.
import { readFileSync, existsSync } from "node:fs";

const URL_ = "https://competition.delphi.fyi/markets.json";

const pick = (o, names) => {
  for (const n of names) {
    const v = n.split(".").reduce((x, k) => (x == null ? x : x[k]), o);
    if (v != null && v !== "") return v;
  }
};
const toTime = (v) => {
  if (v == null) return undefined;
  if (typeof v === "number") return v > 1e12 ? v : v * 1000;
  const t = Date.parse(v);
  return Number.isNaN(t) ? undefined : t;
};
const toProb = (v) => {
  if (v == null) return undefined;
  if (Array.isArray(v)) return toProb(v[0]);
  if (typeof v === "object") return toProb(pick(v, ["yes", "Yes", "YES", "probability"]));
  const n = Number(v);
  if (Number.isNaN(n)) return undefined;
  return n > 1 ? n / 100 : n;
};

export function normalize(m) {
  return {
    address: pick(m, ["marketAddress", "address", "market", "id"]),
    question: pick(m, ["question", "title", "name"]) ?? "(no question)",
    category: pick(m, ["category", "topic"]) ?? "",
    yes: toProb(pick(m, ["odds", "yesProbability", "probability", "impliedProbability", "prices", "yesPrice"])),
    cutoff: toTime(pick(m, ["evidenceCutoff", "evidenceCutoffAt", "cutoff", "cutoffAt", "evidence.cutoff"])),
    close: toTime(pick(m, ["closeTime", "closesAt", "closeAt", "close", "endTime"])),
    criteria: pick(m, ["resolutionCriteria", "criteria", "resolution"]) ?? "",
    sources: pick(m, ["dataSources", "sources", "primarySource"]) ?? [],
  };
}

/** 0..100. Higher = research this first. */
export function score(m, now, used = 0) {
  if (used >= 3) return { score: 0, why: ["all 3 submissions used"] };
  const cutoff = m.cutoff ?? (m.close ? m.close - 24 * 3600e3 : undefined);
  const why = [];
  let s = 50;
  if (cutoff !== undefined) {
    const hours = (cutoff - now) / 3600e3;
    if (hours <= 0) return { score: 0, why: ["evidence cutoff has passed"] };
    if (hours < 3) { s -= 30; why.push(`cutoff in ${hours.toFixed(1)}h: too little time to research`); }
    else if (hours < 48) { s += 10; why.push(`cutoff in ${hours.toFixed(0)}h`); }
    else why.push(`cutoff in ${(hours / 24).toFixed(0)}d`);
  } else { s -= 5; why.push("cutoff unknown: check entry-state"); }
  if (m.yes !== undefined) {
    // 1 at 50%, 0 at 0% or 100%; the guide says there is little to earn outside 20..80.
    const open = 1 - Math.abs(m.yes - 0.5) * 2;
    s += Math.round(open * 30) - (m.yes < 0.2 || m.yes > 0.8 ? 20 : 0);
    why.push(`Yes at ${(m.yes * 100).toFixed(0)}%`);
  } else why.push("odds unknown");
  if (/\b(cpi|inflation|rate|gdp|unemployment|index|temperature|rainfall|count|release|version|vote|ballot|docket|filing|register)\b/i.test(`${m.question} ${m.criteria}`)) {
    s += 10; why.push("answer sits in a primary record or series: calculation or fresh-state evidence is possible");
  }
  s -= used * 8;
  if (used) why.push(`${used} of 3 submissions used`);
  return { score: Math.max(0, Math.min(100, s)), why };
}

/** Counts submissions per market from the shared evidence-log.jsonl that `npm run evidence` writes.
 *  A submit line carries the submission `id`; a claim line (work in progress) does not. */
export function usedCounts(logText) {
  const counts = {};
  for (const line of logText.split("\n")) {
    if (!line.trim()) continue;
    try {
      const e = JSON.parse(line);
      const market = String(e.marketAddress ?? e.market ?? "").toLowerCase();
      if (market && e.id) counts[market] = (counts[market] ?? 0) + 1;
    } catch {}
  }
  return counts;
}

export function rank(raw, now = Date.now(), used = {}) {
  const list = Array.isArray(raw) ? raw : (raw.markets ?? raw.data ?? raw.items ?? []);
  return list
    .map(normalize)
    .map((m) => ({ ...m, ...score(m, now, used[String(m.address).toLowerCase()] ?? 0) }))
    .sort((a, b) => b.score - a.score);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const usedAt = args.indexOf("--used");
  const usedFile = usedAt >= 0 ? args.splice(usedAt, 2)[1] : undefined;
  const raw = args[0] ? JSON.parse(readFileSync(args[0], "utf8")) : await (async () => {
    const r = await fetch(URL_);
    if (!r.ok) { console.error(`Market list not available (${r.status}). It is published when the competition opens, 25 Nov 2026 17:00 UTC.`); process.exit(2); }
    return r.json();
  })();
  const used = usedFile && existsSync(usedFile) ? usedCounts(readFileSync(usedFile, "utf8")) : {};
  for (const m of rank(raw, Date.now(), used)) {
    console.log(`${String(m.score).padStart(3)}  ${m.address}  ${m.question}\n     ${m.why.join("; ")}`);
  }
}
