import { expect, it, vi } from 'vitest';
import { buildPlan, doneTransition, main, seed } from '../scripts/seed-demo.mjs';
import { extractKeywords } from '../src/lib/keywords.js';
import { shipConfidence } from '../src/lib/score.js';

it('builds a complete payments story with three resolved precedents and a blocker', () => {
  const plan = buildPlan();
  expect(plan.projectKey).toBe('PAY');
  expect(plan.issues.filter(issue => issue.resolved)).toHaveLength(3);
  expect(plan.issues.find(issue => issue.id === 'target')).toMatchObject({ resolved: false, summary: 'Enable retry on card authorization timeouts' });
  expect(plan.link).toEqual({ type: 'Blocks', from: 'blocker', to: 'target' });
  expect(plan.pages).toHaveLength(2);
  expect(plan.pages[0].labels).toContain('adr');
  expect(plan.pages.every(page => page.labels.includes('decision'))).toBe(true);
  expect(plan.issues.every(issue => issue.description.includes('Acceptance criteria:'))).toBe(true);
});
it('accepts project/space overrides without leaking env secrets into the plan', () => {
  expect(buildPlan({ PROJECT_KEY: 'CHECK', SPACE_KEY: 'Checkout', ATLASSIAN_API_TOKEN: 'secret' })).toMatchObject({ projectKey: 'CHECK', spaceKey: 'Checkout' });
  expect(JSON.stringify(buildPlan({ ATLASSIAN_API_TOKEN: 'secret' }))).not.toContain('secret');
});
it('keeps seeded ADR text discoverable and yields the documented baseline score', () => {
  const plan = buildPlan();
  const target = plan.issues.find(issue => issue.id === 'target');
  const issue = { key: 'PAY-5', fields: { summary: target.summary, labels: target.labels, description: { type: 'doc', content: [{ type: 'text', text: target.description }] }, issuelinks: [{ type: { inward: 'is blocked by' }, inwardIssue: { key: 'PAY-4', fields: { status: { statusCategory: { key: 'new' } }, issuetype: { name: 'Task' } } } }] } };
  for (const keyword of extractKeywords(issue)) expect(plan.pages.every(page => page.text.toLowerCase().includes(keyword))).toBe(true);
  const precedent = { issues: plan.issues.filter(issue => issue.resolved).map(issue => ({ kind: issue.labels.includes('incident') ? 'incident' : 'bug' })) };
  expect(shipConfidence(issue, precedent).score).toBe(67);
  expect(shipConfidence(issue, { ...precedent, decisions: [{ issueKey: 'PAY-5', status: 'accepted' }] }).score).toBe(72);
});
it('rejects empty or unsafe project and space keys', () => {
  for (const PROJECT_KEY of ['', 'pay', 'PAY" OR 1=1']) expect(() => buildPlan({ PROJECT_KEY })).toThrow('PROJECT_KEY');
  for (const SPACE_KEY of ['', '<space>', 'a/b']) expect(() => buildPlan({ SPACE_KEY })).toThrow('SPACE_KEY');
});
it('selects by category rather than localized status name and rejects missing done transitions', () => {
  expect(doneTransition([{ id: '1', to: { name: 'Done', statusCategory: { key: 'new' } } }, { id: '2', to: { name: 'Terminé', statusCategory: { key: 'done' } } }]).id).toBe('2');
  expect(() => doneTransition([])).toThrow('No available transition');
});
it('dry-run needs no credentials and never invokes fetch', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network forbidden'));
  const log = vi.spyOn(console, 'log').mockImplementation(() => {});
  try { await main(['--dry-run'], {}); expect(fetcher).not.toHaveBeenCalled(); expect(log).toHaveBeenCalledWith('DRY RUN: no network requests; no credentials required.'); }
  finally { fetcher.mockRestore(); log.mockRestore(); }
});
it('rejects missing credentials, unexpected flags and unsafe sites before networking', async () => {
  await expect(main([], {})).rejects.toThrow('ATLASSIAN_SITE');
  await expect(main(['--typo'], {})).rejects.toThrow('Usage');
  await expect(seed(buildPlan(), { site: 'https://evil.example', email: 'x', token: 'x' })).rejects.toThrow('ATLASSIAN_SITE');
  await expect(seed(buildPlan(), { site: 'https://demo.atlassian.net' })).rejects.toThrow('ATLASSIAN_EMAIL');
});
it('creates and resolves the story, then reuses it without duplicate issues, pages or links', async () => {
  const plan = buildPlan();
  let project = false, space = false, links = [], issues = [], pages = [];
  const writes = [];
  const fetcher = vi.fn(async (url, options) => {
    const path = url.pathname;
    const body = options.body ? JSON.parse(options.body) : undefined;
    const reply = (value, status = 200) => new Response(value === undefined ? null : JSON.stringify(value), { status });
    if (options.method === 'POST' && !path.endsWith('/search/jql')) writes.push(path);
    if (path === '/rest/api/3/myself') return reply({ accountId: 'rayhan' });
    if (path === '/rest/api/3/project/PAY') return project ? reply({ issueTypes: [{ id: 'bug', name: 'Bug' }, { id: 'task', name: 'Task' }] }) : reply({}, 404);
    if (path === '/rest/api/3/project') { project = true; return reply({ id: 'p' }, 201); }
    if (path.endsWith('/search/jql')) return reply({ issues, isLast: true });
    if (path === '/rest/api/3/issue') { const issue = { key: `PAY-${issues.length + 1}`, fields: { ...body.fields, status: { statusCategory: { key: 'new' } }, resolution: null } }; issues.push(issue); return reply(issue, 201); }
    const issue = issues.find(issue => path.startsWith(`/rest/api/3/issue/${issue.key}`));
    if (path.endsWith('/transitions')) {
      if (options.method === 'GET') return reply({ transitions: [{ id: 'finish', to: { id: 'done' }, fields: { resolution: { allowedValues: [{ id: 'fixed', name: 'Fixed' }] } } }] });
      expect(body.fields.resolution.id).toBe('fixed');
      issue.fields.status.statusCategory.key = 'done'; issue.fields.resolution = { id: 'fixed' }; return reply(undefined, 204);
    }
    if (path === '/rest/api/3/status/done') return reply({ statusCategory: { key: 'done' } });
    if (issue) return reply({ ...issue, fields: { ...issue.fields, issuelinks: links } });
    if (path === '/rest/api/3/issueLinkType') return reply({ issueLinkTypes: [{ id: 'blocks', inward: 'is blocked by', outward: 'blocks' }] });
    if (path === '/rest/api/3/issueLink') { links.push({ inwardIssue: body.inwardIssue, type: body.type }); return reply(undefined, 201); }
    if (path === '/wiki/rest/api/space/PAY') return space ? reply({ key: 'PAY' }) : reply({}, 404);
    if (path === '/wiki/rest/api/space') { space = true; return reply({ key: 'PAY' }); }
    if (path === '/wiki/rest/api/content') {
      if (options.method === 'GET') return reply({ results: pages.filter(page => page.title === url.searchParams.get('title')) });
      const page = { id: `${pages.length + 1}`, title: body.title }; pages.push(page); return reply(page);
    }
    if (path.endsWith('/label')) return reply({ results: body });
    throw new Error(`Unexpected request: ${path}`);
  });
  const options = { site: 'https://demo.atlassian.net', email: 'rayhan@example.com', token: 'fake-test-token', fetcher, log: vi.fn() };
  expect(await seed(plan, options)).toMatchObject({ target: 'PAY-5', blocker: 'PAY-4' });
  expect(issues.filter(issue => issue.fields.resolution)).toHaveLength(3);
  const count = writes.length;
  await seed(plan, options);
  expect(writes.slice(count)).toEqual(['/wiki/rest/api/content/1/label', '/wiki/rest/api/content/2/label']);
  expect(issues).toHaveLength(5); expect(pages).toHaveLength(2); expect(links).toHaveLength(1);
});
it('stops on REST errors without logging response data or credentials', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response('sensitive body', { status: 403 }));
  await expect(seed(buildPlan(), { site: 'https://demo.atlassian.net', email: 'x', token: 'secret', fetcher })).rejects.toThrow('failed (403)');
  expect(fetcher).toHaveBeenCalledTimes(1);
});
