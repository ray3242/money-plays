import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ store: new Map(), getMany: vi.fn(), query: {} }));
vi.mock('@forge/api', () => ({ default: {}, route: vi.fn() }));
vi.mock('@forge/kvs', () => ({
  kvs: {
    set: vi.fn(async (key, value) => mocks.store.set(key, value)),
    get: vi.fn(async key => mocks.store.get(key)),
    query: () => mocks.query
  }, WhereConditions: { beginsWith: value => ({ beginsWith: value }) }
}));
import { createDecision, getDecision, listDecisions, searchDecisions, supersedeDecision } from '../src/lib/decisions.js';
const input = { title: 'Use queue', decision: 'Process asynchronously', rationale: 'Avoid timeouts', issueKey: 'APP-1', projectKey: 'APP', tags: ['queue'] };
beforeEach(() => {
  mocks.store.clear();
  mocks.query = { where: vi.fn().mockReturnThis(), limit: vi.fn().mockReturnThis(), cursor: vi.fn().mockReturnThis(), getMany: mocks.getMany };
  mocks.getMany.mockReset().mockImplementation(async () => ({ results: [...mocks.store].map(([key, value]) => ({ key, value })) }));
});
describe('decision ledger', () => {
  it('creates authenticated entries, ignores forged authors, and reads them', async () => {
    const entry = await createDecision({ ...input, authorAccountId: 'forged' }, 'ada');
    expect(entry).toMatchObject({ status: 'accepted', authorAccountId: 'ada', tags: ['queue'] });
    expect(await getDecision(entry.id)).toEqual(entry);
    expect([...mocks.store.keys()][0]).toMatch(/^decision:\d{13}-/);
  });
  it.each([{ title: '' }, { title: 'x'.repeat(121) }, { decision: 'x'.repeat(2001) }, { rationale: 'x'.repeat(2001) }, { tags: Array(9).fill('a') }, { tags: [2] }, { status: 'bad' }, { status: 'superseded' }, { issueKey: 'bad' }, { projectKey: 'bad' }])('rejects invalid create %j', async changes => {
    await expect(createDecision({ ...input, ...changes }, 'ada')).rejects.toThrow();
    expect(mocks.store.size).toBe(0);
  });
  it('requires identity, validates ids and handles missing', async () => {
    await expect(createDecision(input)).rejects.toThrow('Authenticated');
    await expect(getDecision('../bad')).rejects.toThrow('Invalid decision id');
    expect(await getDecision(`1234567890123-${'a'.repeat(36)}`)).toBeUndefined();
  });
  it('paginates KVS, sorts newest first globally, filters and handles empty', async () => {
    expect(await searchDecisions('')).toEqual([]);
    const a = { ...input, id: 'a', status: 'accepted', createdAt: '2026-01-01' };
    const b = { ...a, id: 'b', createdAt: '2026-02-01', status: 'proposed', title: 'Cache' };
    mocks.getMany.mockResolvedValueOnce({ results: [{ value: a }], nextCursor: 'kvs-next' }).mockResolvedValueOnce({ results: [{ value: b }] });
    expect((await listDecisions({ limit: 1 })).entries).toEqual([b]);
    expect(mocks.query.cursor).toHaveBeenCalledWith('kvs-next');
    mocks.getMany.mockResolvedValue({ results: [{ value: a }, { value: b }] });
    expect((await listDecisions({ cursor: 'offset:1', limit: 1 })).entries).toEqual([a]);
    expect(await searchDecisions('queue', { status: 'accepted', projectKey: 'APP', issueKey: 'APP-1' })).toEqual([a]);
    expect(await searchDecisions('no match')).toEqual([]);
    await expect(searchDecisions('', { status: 'oops' })).rejects.toThrow('status');
    await expect(searchDecisions(3)).rejects.toThrow('query');
    await expect(listDecisions({ cursor: 'bad' })).rejects.toThrow('cursor');
  });
  it('caps scans at 500 and propagates storage errors', async () => {
    mocks.getMany.mockResolvedValue({ results: Array.from({ length: 100 }, (_, i) => ({ value: { ...input, id: `${i}`, status: 'accepted', createdAt: '2026' } })), nextCursor: 'next' });
    expect(await searchDecisions('')).toHaveLength(500);
    expect(mocks.getMany).toHaveBeenCalledTimes(5);
    mocks.getMany.mockRejectedValue(new Error('storage down'));
    await expect(listDecisions()).rejects.toThrow('storage down');
  });
  it('supersedes only with accepted replacement and original author', async () => {
    const a = await createDecision(input, 'ada');
    const b = await createDecision(input, 'bob');
    await expect(supersedeDecision(a.id, a.id, 'ada')).rejects.toThrow('different');
    await expect(supersedeDecision(a.id, b.id, 'bob')).rejects.toThrow('author');
    expect(await supersedeDecision(a.id, b.id, 'ada')).toMatchObject({ status: 'superseded', supersededBy: b.id });
    await expect(supersedeDecision(a.id, b.id, 'ada')).rejects.toThrow('Replacement');
    await expect(supersedeDecision(b.id, a.id, 'bob')).rejects.toThrow('Replacement');
    await expect(supersedeDecision(b.id, `1234567890123-${'a'.repeat(36)}`, 'bob')).rejects.toThrow('not found');
  });
});
