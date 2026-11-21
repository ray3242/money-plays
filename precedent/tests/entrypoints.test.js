import { beforeEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ build: vi.fn(), visible: vi.fn(), record: vi.fn(), replace: vi.fn() }));
vi.mock('../src/lib/precedent.js', () => ({ buildPrecedent: mocks.build }));
vi.mock('../src/lib/ledger-access.js', () => ({ visibleDecisions: mocks.visible, recordDecision: mocks.record, replaceDecision: mocks.replace }));
vi.mock('@forge/api', () => ({ default: {}, route: vi.fn() }));
vi.mock('@forge/resolver', () => ({ default: class { define() {} getDefinitions() { return {}; } } }));
import { getIssuePrecedent, assessShipReadiness, searchDecisionsAction, recordDecisionAction } from '../src/actions.js';
import { definitions } from '../src/resolver.js';
const context = { accountId: 'ada', extension: { issue: { key: 'APP-1' }, project: { key: 'APP' } } };
beforeEach(() => {
  vi.resetAllMocks();
  mocks.build.mockResolvedValue({ issue: { key: 'APP-1', fields: {} }, issues: [], pages: [], keywords: [], decisions: [], people: [], graph: { items: [] }, warnings: [] });
  mocks.visible.mockResolvedValue([]); mocks.record.mockResolvedValue({ id: 'new' });
});
it('actions use direct or product context keys, compact evidence and score factors', async () => {
  expect(await getIssuePrecedent({ context: { jira: { issueKey: 'APP-1' } } })).toMatchObject({ issueKey: 'APP-1', url: '/browse/APP-1' });
  expect(await assessShipReadiness({ issueKey: 'APP-1' })).toMatchObject({ score: 90, grade: 'Ready' });
  expect(mocks.build).toHaveBeenCalledWith('APP-1');
});
it.each([undefined, {}, { issueKey: 'APP-1 OR 1=1' }, { issueKey: 'a-1' }])('actions reject invalid keys %j', async payload => {
  await expect(getIssuePrecedent(payload)).rejects.toThrow('Invalid issue key');
  expect(mocks.build).not.toHaveBeenCalled();
});
it('search returns bounded entries and propagates errors', async () => {
  mocks.visible.mockResolvedValueOnce(Array(40).fill({ title: 'Entry' }));
  expect((await searchDecisionsAction({ query: 'queue' })).decisions).toHaveLength(30);
  expect(mocks.visible).toHaveBeenCalledWith('queue', {});
  mocks.visible.mockRejectedValueOnce(new Error('denied'));
  await expect(searchDecisionsAction({ query: '' })).rejects.toThrow('denied');
});
it('record action whitelists fields, falls back issue and supplies trusted invocation context', async () => {
  await recordDecisionAction({ title: 'Queue', decision: 'Use queue', rationale: 'Scale', authorAccountId: 'forged', context: { jira: { issueKey: 'APP-1' } } }, context);
  expect(mocks.record).toHaveBeenCalledWith({ title: 'Queue', decision: 'Use queue', rationale: 'Scale', issueKey: 'APP-1' }, context);
  await expect(recordDecisionAction({ issueKey: 'bad' }, context)).rejects.toThrow('Invalid issue');
});
it('resolver context overrides spoofed issue/project and validates absent context', async () => {
  expect(await definitions.getIssueContext({ payload: { issueKey: 'OTHER-9' }, context })).toHaveProperty('confidence');
  expect(mocks.build).toHaveBeenCalledWith('APP-1');
  await definitions.recordDecision({ payload: { issueKey: 'OTHER-9', title: 'Decision' }, context });
  expect(mocks.record.mock.calls[0][0].issueKey).toBe('APP-1');
  await definitions.listDecisions({ payload: { projectKey: 'OTHER', status: 'accepted', query: 'queue' }, context });
  expect(mocks.visible).toHaveBeenCalledWith('queue', { projectKey: 'APP', status: 'accepted' });
  await expect(definitions.getIssueContext({ context: {} })).rejects.toThrow('Invalid issue');
  await expect(definitions.listDecisions({ context: {} })).rejects.toThrow('Authenticated');
  await expect(definitions.listDecisions({ payload: { projectKey: 'bad' }, context: { accountId: 'ada' } })).rejects.toThrow('project');
});
it('resolver forwards supersede identifiers and identity', async () => {
  await definitions.supersedeDecision({ payload: { id: 'one', byId: 'two' }, context });
  expect(mocks.replace).toHaveBeenCalledWith('one', 'two', context);
});
it('records unlinked project-page decisions in the trusted project and validates it', async () => {
  const projectContext = { accountId: 'ada', extension: { project: { key: 'APP' } } };
  await definitions.recordDecision({ payload: { title: 'Decision', projectKey: 'OTHER' }, context: projectContext });
  expect(mocks.record).toHaveBeenCalledWith({ title: 'Decision', projectKey: 'APP' }, projectContext);
  mocks.record.mockClear();
  for (const key of ['', 'bad', 'APP OR 1=1']) {
    await expect(definitions.recordDecision({ payload: { title: 'Decision' }, context: { ...projectContext, extension: { project: { key } } } })).rejects.toThrow('Invalid project key');
  }
  expect(mocks.record).not.toHaveBeenCalled();
  await definitions.recordDecision({ payload: { title: 'Decision' }, context: { accountId: 'ada' } });
  expect(mocks.record).toHaveBeenCalledWith({ title: 'Decision' }, { accountId: 'ada' });
});
it('evidence actions propagate underlying permission/API errors', async () => {
  mocks.build.mockRejectedValue(new Error('403'));
  await expect(assessShipReadiness({ issueKey: 'APP-1' })).rejects.toThrow('403');
});
