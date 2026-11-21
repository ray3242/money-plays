// Drives the web UI through the whole story and records it.
//   URL="http://localhost:5173/?rpc=…" node scripts/walkthrough.mjs
// Doubles as the UI end-to-end test: it exits non-zero if any step's outcome is wrong.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const url = process.env.URL;
if (!url) throw new Error("Set URL to the page to drive");
const out = process.env.OUT ?? "demo";
const pause = Number(process.env.PAUSE ?? 1800);
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, recordVideo: { dir: out, size: { width: 1600, height: 900 } } });
const page = await context.newPage();
page.setDefaultTimeout(120_000);
let step = 0;

async function caption(text) {
  await page.evaluate((t) => {
    let el = document.getElementById("caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "caption";
      el.style.cssText = "position:fixed;right:24px;top:16px;background:#000d;color:#fff;padding:12px 22px;border-radius:10px;font-size:18px;font-weight:600;z-index:99;max-width:640px;text-align:center;border:1px solid #34d399";
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, text);
  console.log(`[${++step}] ${text}`);
  await page.waitForTimeout(pause);
}
const shot = (name) => page.screenshot({ path: `${out}/${String(step).padStart(2, "0")}-${name}.png` });
/** Click, then wait until the page has finished the transaction and re-read the chain. */
async function act(selector) {
  const before = await page.locator("#log .e.good, #log .e.err").count();
  await page.locator(selector).first().click();
  await page.waitForFunction((n) => document.querySelectorAll("#log .e.good, #log .e.err").length > n && document.body.style.cursor === "", before);
  await page.waitForTimeout(400);
}
async function expectText(selector, re, what) {
  const text = await page.locator(selector).innerText();
  if (!re.test(text)) throw new Error(`Step ${step} (${what}): expected ${re} in:\n${text}`);
}
async function invoice(preset) {
  await page.locator(`#seller button:has-text("${preset}")`).click();
  await page.waitForTimeout(pause / 3);
  await act('[data-act="createInvoice"]');
}

await page.goto(url);
await page.waitForSelector("#biz .who");
await caption("Leash: a business gives its AI agent a budget, not its wallet.");

if (await page.locator('[data-act="mint"]').count()) await act('[data-act="mint"]');
await caption("The business deposits stablecoins into its own vault on Aevum.");
await page.fill("#f-amt", "8");
await act('[data-act="deposit"]');
await expectText("#biz", /In the vault\s*8 tUSD8/, "deposit");

await caption("It creates a leash: 5 tUSD8 a day, at most 2 per payment, 7 days, only to acme-cloud.");
await act('[data-act="createLeash"]');
await expectText("#biz", /Leash #\d+\s*active/, "leash");
await shot("leash");

await caption("A merchant registers a confirmed name, so payers see a name instead of a hex address.");
await act('[data-act="register"]');
await expectText("#seller", /Confirmed name\s*acme-cloud/, "register");

await caption("The merchant sends an ordinary invoice for 1 tUSD8.");
await invoice("Normal invoice");
await expectText("#agent", /agent will pay/, "agent approves");
await caption("The agent checks it: confirmed payee, inside cap, budget and allowlist. It signs. It holds no funds and no gas.");
await shot("approved");
await act('[data-act="relayAll"]');
await expectText("#agent", /paid by agent/, "paid");
await expectText("#seller", /Received\s*1 tUSD8/, "merchant received");
await caption("The merchant submits the signature and is paid from the vault. The budget meter moves.");
await shot("paid");

await caption("Now an invoice above the per-payment cap.");
await invoice("Over the cap");
await expectText("#biz", /over the per-payment cap/, "cap escalation");
await caption("The contract would refuse it, so the agent does not sign. It goes to the owner with the reason.");
await shot("over-cap");

await caption("A prompt injection hidden in an invoice memo.");
await invoice("Prompt injection");
await expectText("#biz", /memo text is never followed/, "injection escalation");
await caption("Memo text is data, never instructions. Escalated, not paid.");
await shot("injection");

await caption("An impostor registers a lookalike name: acme-c1oud, with a digit 1.");
await page.locator('[data-who="impostor"]').click();
await page.waitForSelector("#f-name");
await act('[data-act="register"]');
await caption("Suppose the owner is fooled and even adds the lookalike to the allowlist.");
await page.fill("#f-allow", "acme-c1oud");
await act('[data-act="allow"]');
await invoice("Lookalike invoice");
await expectText("#biz", /looks like the trusted payee "acme-cloud"/, "lookalike escalation");
await caption("The agent still refuses: the name imitates a payee it already trusts.");
await shot("lookalike");
await invoice("Redirect scam");
await expectText("#agent", /names a different wallet to pay/, "redirect escalation");
await expectText("#seller", /Received\s*0 tUSD8/, "impostor got nothing");
await caption("Four attacks, zero paid. The impostor has received nothing.");

await caption("The owner reviews the over-cap invoice and pays it directly. That does not use the agent's budget.");
await act('#biz .card:has-text("Annual support plan") [data-act="payAsOwner"]');
await expectText("#agent", /paid by owner/, "owner pay");
await shot("owner-paid");

await caption("One click cuts the leash. Every signature the agent ever made stops working in the same block.");
await page.locator('[data-who="merchant"]').click();
await invoice("Normal invoice");
await act('[data-act="revoke"]');
await expectText("#biz", /revoked/, "revoke");
await expectText("#biz", /owner revoked this leash/, "revoked escalation");
await shot("revoked");
await caption("Leash: open source, github.com/ray3242/money-plays");
await page.waitForTimeout(pause);

const video = page.video();
await context.close();
await browser.close();
console.log("PASS. Video:", await video.path());
