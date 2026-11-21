import { beforeEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ issue: vi.fn(), search: vi.fn(), create: vi.fn(), get: vi.fn(), supersede: vi.fn() }));
vi.mock('../src/lib/jira.js', () => ({ getIssue: mocks.issue }));
vi.mock('../src/lib/decisions.js', () => ({ createDecision: mocks.create, searchDecisions: mocks.search, getDecision: mocks.get, supersedeDecision: mocks.supersede }));
import { visibleDecisions, recordDecision, replaceDecision } from '../src/lib/ledger-access.js';
beforeEach(() => vi.resetAllMocks());
it('hides issue-linked records when issue permission is denied', async () => {
  mocks.search.mockResolvedValue([{ id: 'a', issueKey: 'APP-1' }, { id: 'b', issueKey: 'APP-2' }, { id: 'c' }]);
  mocks.issue.mockImplementation(async key => { if (key === 'APP-2') throw new Error('403'); return {}; });
  expect((await visibleDecisions()).map(entry => entry.id)).toEqual(['a', 'c']);
});
it('requires identity and accessible linked issue before creation', async () => {
  await expect(recordDecision({})).rejects.toThrow('Authenticated');
  mocks.issue.mockRejectedValueOnce(new Error('403'));
  await expect(recordDecision({ issueKey: 'APP-1' }, { accountId: 'ada' })).rejects.toThrow('403');
  expect(mocks.create).not.toHaveBeenCalled();
  mocks.issue.mockResolvedValue({});
  await recordDecision({ issueKey: 'APP-1', projectKey: 'OTHER' }, { accountId: 'ada' });
  expect(mocks.create).toHaveBeenCalledWith({ issueKey: 'APP-1', projectKey: 'APP' }, 'ada');
});
it('authorizes both source and replacement issue before superseding', async () => {
  mocks.get.mockImplementation(async id => ({ issueKey: id === 'a' ? 'APP-1' : 'APP-2' }));
  mocks.issue.mockResolvedValue({});
  await replaceDecision('a', 'b', { accountId: 'ada' });
  expect(mocks.issue.mock.calls.map(call => call[0])).toEqual(['APP-1', 'APP-2']);
  expect(mocks.supersede).toHaveBeenCalledWith('a', 'b', 'ada');
});
it('preserves an unlinked decision project key when recording', async () => {
  await recordDecision({ title: 'Decision', projectKey: 'APP' }, { accountId: 'ada' });
  expect(mocks.create).toHaveBeenCalledWith({ title: 'Decision', projectKey: 'APP' }, 'ada');
  expect(mocks.issue).not.toHaveBeenCalled();
});
