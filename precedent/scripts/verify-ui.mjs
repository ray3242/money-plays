import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';

await mkdir('docs/screenshots', { recursive: true });
const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}), headless: true, args: ['--no-sandbox'] });
const errors = [];
const page = await browser.newPage({ viewport: { width: 700, height: 1100 }, reducedMotion: 'reduce' });
page.on('pageerror', error => errors.push(error.message));
async function capture(url, path, width, height = 1100) {
  await page.setViewportSize({ width, height });
  await page.goto(url);
  await page.getByRole('heading', { name: width === 1280 ? 'Decision ledger' : 'Enable retry on card authorization timeouts', exact: true }).waitFor();
  await page.locator('.loading').waitFor({ state: 'detached' });
  if (width === 1280) await page.getByRole('button', { name: 'Supersede decision', exact: true }).waitFor();
  await page.screenshot({ path: `docs/screenshots/${path}.png`, fullPage: true, animations: 'disabled' });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  if (overflow) throw new Error(`Horizontal overflow at ${width}px: ${path}`);
}
try {
  await capture('http://localhost:4173', 'panel-light', 700);
  await page.getByText('Gateway reconciliation is still blocking').click();
  await page.screenshot({ path: 'docs/screenshots/panel-evidence.png', fullPage: true });
  await page.getByRole('tab', { name: /Decisions/ }).click();
  await page.getByRole('button', { name: /^Record$/ }).click();
  await page.getByLabel('Title', { exact: false }).fill('Retry after gateway reconciliation');
  await page.getByRole('textbox', { name: 'Decision *', exact: true }).fill('Wait for reconciliation before a retry.');
  await page.getByLabel('Rationale', { exact: false }).fill('A timeout is not a failed authorization.');
  await page.getByRole('form', { name: 'Record a decision' }).getByRole('button', { name: 'Record decision', exact: true }).click();
  await page.getByText('Decision recorded. The next person has the context.').waitFor();
  await page.evaluate(() => localStorage.removeItem('precedent-demo-decisions'));
  await capture('http://localhost:4173?theme=dark', 'panel-dark', 700);
  await capture('http://localhost:4174', 'ledger-light', 1280, 1000);
  await page.getByRole('button', { name: 'Supersede decision', exact: true }).click();
  await page.getByRole('combobox').selectOption('decision-4');
  await page.getByRole('button', { name: 'Confirm replacement', exact: true }).click();
  await page.getByText('Decision superseded. The original reasoning stays on record.').waitFor();
  await page.getByRole('button', { name: /Cap automatic retries/ }).click();
  await page.getByText('Only the author can supersede this decision.').waitFor();
  await page.getByRole('button', { name: 'proposed', exact: true }).click();
  await page.getByText('1 decision on record', { exact: true }).waitFor();
  await page.getByRole('textbox', { name: 'Search decisions' }).fill('no matching record');
  await page.getByRole('heading', { name: 'No decisions match this view' }).waitFor();
  await page.goto('http://localhost:4173?state=error');
  await page.getByRole('button', { name: 'Try again' }).waitFor();
  await page.screenshot({ path: 'docs/screenshots/panel-error.png', fullPage: true });
  await page.goto('http://localhost:4173?state=empty');
  await page.getByText('No close precedents yet').waitFor();
  await page.screenshot({ path: 'docs/screenshots/panel-empty.png', fullPage: true });
  await capture('http://localhost:4173', 'panel-narrow', 390);
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('UI verified: panel light/dark, expandable evidence, record + success, ledger details + author-only supersede, filters/search, empty/error states; no page errors or horizontal overflow.');
} finally { await browser.close(); }
