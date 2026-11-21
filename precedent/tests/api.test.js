import { beforeEach, describe, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ jira: vi.fn(), confluence: vi.fn(), graph: vi.fn() }));
vi.mock('@forge/api', () => ({ default: { asUser: () => ({ requestJira: mocks.jira, requestConfluence: mocks.confluence, requestTeamworkGraph: mocks.graph }) }, route: (strings, ...values) => strings.reduce((out, part, i) => out + part + (i < values.length ? encodeURIComponent(values[i]) : ''), '') }));
import { getIssue, searchJql } from '../src/lib/jira.js';
import { searchCql } from '../src/lib/confluence.js';
import { relatedWork } from '../src/lib/twg.js';
const ok = data => ({ ok: true, json: async () => data });
beforeEach(() => vi.resetAllMocks());
describe('product API adapters', () => {
  it('gets an issue as user, expands changelog and enriches historical categories', async () => {
    mocks.jira.mockResolvedValueOnce(ok({ key: 'APP-1' })).mockResolvedValueOnce(ok([{ statuses: [{ id: '9', statusCategory: { key: 'done' } }] }]));
    expect(await getIssue('APP-1')).toMatchObject({ key: 'APP-1', statusCategories: { 9: 'done' } });
    expect(mocks.jira.mock.calls[0][0]).toContain('expand=changelog');
    expect(mocks.jira.mock.calls[1][0]).toContain('/project/APP/statuses');
    await expect(getIssue('bad')).rejects.toThrow('Invalid issue');
  });
  it('denies inaccessible issues but degrades status enrichment', async () => {
    mocks.jira.mockResolvedValueOnce({ ok: false, status: 403 });
    await expect(getIssue('APP-1')).rejects.toThrow('403');
    mocks.jira.mockResolvedValueOnce(ok({ key: 'APP-1' })).mockRejectedValueOnce(new Error('denied'));
    expect((await getIssue('APP-1')).statusCategoryWarning).toContain('unavailable');
  });
  it('uses enhanced POST JQL, explicit fields, bounded max and empty defaults', async () => {
    mocks.jira.mockResolvedValue(ok({ issues: [{ key: 'APP-2' }] }));
    expect(await searchJql('project = APP', ['summary'], 8)).toEqual([{ key: 'APP-2' }]);
    const [url, request] = mocks.jira.mock.calls[0];
    expect(url).toBe('/rest/api/3/search/jql');
    expect(JSON.parse(request.body)).toEqual({ jql: 'project = APP', fields: ['summary'], maxResults: 8 });
    mocks.jira.mockResolvedValueOnce(ok({}));
    expect(await searchJql('x')).toEqual([]);
    mocks.jira.mockResolvedValueOnce({ ok: false, status: 429 });
    await expect(searchJql('x')).rejects.toThrow('429');
  });
  it('encodes CQL, maps links/excerpts and handles missing result/denial', async () => {
    mocks.confluence.mockResolvedValueOnce(ok({ _links: { base: 'https://site.atlassian.net/wiki' }, results: [{ content: { id: '1' }, title: 'ADR', url: '/spaces/APP/pages/1', excerpt: '<b>Queue</b>', lastModified: '2026' }] }));
    expect(await searchCql('text ~ "queue"')).toEqual([{ id: '1', title: 'ADR', url: 'https://site.atlassian.net/wiki/spaces/APP/pages/1', excerpt: 'Queue', lastModified: '2026', labels: [] }]);
    expect(mocks.confluence.mock.calls[0][0]).toContain('text%20~%20%22queue%22');
    mocks.confluence.mockResolvedValueOnce(ok({}));
    expect(await searchCql('x')).toEqual([]);
    mocks.confluence.mockResolvedValueOnce({ ok: false, status: 403 });
    await expect(searchCql('x')).rejects.toThrow('403');
  });
});
describe('Teamwork Graph curated enrichment', () => {
  const issue = { fields: { assignee: { accountId: 'ada' } } };
  it('uses current assignee ARI with documented query', async () => {
    mocks.graph.mockResolvedValueOnce(ok({ data: { atlassianUserAssignedJiraWorkItems: { edges: [{ node: { id: 'ari:issue:2', title: 'Queue' } }] } } }));
    expect((await relatedWork(issue)).items).toEqual([{ id: 'ari:issue:2', title: 'Queue' }]);
    expect(mocks.graph.mock.calls[0][0]).toContain('atlassianUserAssignedJiraWorkItems');
    expect(mocks.graph.mock.calls[0][1]).toEqual({ userId: 'ari:cloud:identity::user/ada' });
  });
  it('skips no assignee, empty, HTTP errors, GraphQL errors and runtime errors', async () => {
    expect((await relatedWork({})).note).toContain('no assignee');
    for (const response of [ok({ data: {} }), { ok: false }, ok({ errors: [{ message: 'denied' }] })]) {
      mocks.graph.mockResolvedValueOnce(response);
      expect(await relatedWork(issue)).toMatchObject({ items: [], note: expect.any(String) });
    }
    mocks.graph.mockRejectedValueOnce(new Error('network'));
    expect((await relatedWork(issue)).note).toContain('unavailable');
  });
});
