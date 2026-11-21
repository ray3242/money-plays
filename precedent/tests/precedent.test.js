import { beforeEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ getIssue: vi.fn(), searchJql: vi.fn(), searchCql: vi.fn(), ledger: vi.fn(), graph: vi.fn() }));
vi.mock('../src/lib/jira.js', () => ({ getIssue: mocks.getIssue, searchJql: mocks.searchJql, issueUrl: key => `/browse/${key}` }));
vi.mock('../src/lib/confluence.js', () => ({ searchCql: mocks.searchCql }));
vi.mock('../src/lib/ledger-access.js', () => ({ visibleDecisions: mocks.ledger }));
vi.mock('../src/lib/twg.js', () => ({ relatedWork: mocks.graph }));
import { buildPrecedent, precedentKind } from '../src/lib/precedent.js';
beforeEach(() => {
  vi.resetAllMocks();
  mocks.getIssue.mockResolvedValue({ key: 'APP-1', fields: { summary: 'Queue latency', components: [{ name: 'Gateway' }] } });
  mocks.searchJql.mockResolvedValue([]); mocks.searchCql.mockResolvedValue([]); mocks.ledger.mockResolvedValue([]); mocks.graph.mockResolvedValue({ items: [], note: 'Graph skipped' });
});
it('orchestrates bounded relevant evidence, overlap ranking, decisions and people', async () => {
  const assignee = { accountId: 'ada', displayName: 'Ada' };
  mocks.searchJql.mockResolvedValue([
    { key: 'APP-2', fields: { summary: 'Queue', assignee, labels: ['incident'] } },
    { key: 'APP-3', fields: { summary: 'Queue latency', assignee, issuetype: { name: 'Bug' } } },
    { key: 'APP-4', fields: { summary: 'Other' } }
  ]);
  mocks.searchCql.mockResolvedValue([{ id: 'p1', title: 'Queue decision', url: '/wiki/p1' }]);
  mocks.ledger.mockResolvedValue([
    { id: 'a', issueKey: 'APP-1', tags: [], title: '', decision: '' },
    { id: 'b', tags: ['gateway'], title: '', decision: '' },
    { id: 'c', tags: [], title: 'queue', decision: '' },
    { id: 'd', tags: [], title: 'unrelated', decision: '' }
  ]);
  const result = await buildPrecedent('APP-1');
  expect(result.issues[0]).toMatchObject({ key: 'APP-3', relevance: 2, kind: 'bug' });
  expect(result.issues[1].kind).toBe('incident');
  expect(result.people).toEqual([{ ...assignee, count: 2, issueKeys: ['APP-3', 'APP-2'] }]);
  expect(result.decisions.map(entry => entry.id)).toEqual(['a', 'b', 'c']);
  expect(result.pages).toHaveLength(1);
  expect(mocks.searchJql.mock.calls[0][0]).toContain('resolution IS NOT EMPTY AND key != "APP-1"');
  expect(mocks.searchJql.mock.calls[0][0]).toContain('ORDER BY resolved DESC');
  expect(mocks.searchCql.mock.calls[0][0]).toContain('label IN ("decision", "adr", "decision-record")');
});
it('survives Confluence failure, reports graph note and empty result', async () => {
  mocks.searchCql.mockRejectedValue(new Error('not installed'));
  const result = await buildPrecedent('APP-1');
  expect(result.pages).toEqual([]);
  expect(result.warnings).toContain('Confluence decision search unavailable; check installation and permissions.');
  expect(result.warnings).toContain('Graph skipped');
});
it('skips keyword searches on empty inputs and warns about partial history', async () => {
  mocks.getIssue.mockResolvedValue({ key: 'APP-1', fields: {}, changelog: { total: 10, histories: [] } });
  const result = await buildPrecedent('APP-1');
  expect(result.issues).toEqual([]);
  expect(mocks.searchJql).not.toHaveBeenCalled();
  expect(mocks.searchCql).not.toHaveBeenCalled();
  expect(result.warnings.some(note => note.includes('partial'))).toBe(true);
});
it('propagates Jira and ledger errors rather than showing falsely complete data', async () => {
  mocks.getIssue.mockRejectedValueOnce(new Error('403'));
  await expect(buildPrecedent('APP-1')).rejects.toThrow('403');
  mocks.ledger.mockRejectedValueOnce(new Error('storage'));
  await expect(buildPrecedent('APP-1')).rejects.toThrow('storage');
});
it.each([['hotfix', 'incident'], ['regression', 'incident'], ['revert', 'revert'], ['rollback', 'revert']])('classifies %s', (label, kind) => {
  expect(precedentKind({ fields: { labels: [label] } })).toBe(kind);
});
