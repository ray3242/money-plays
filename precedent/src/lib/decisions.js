import { randomUUID } from 'node:crypto';
import { kvs, WhereConditions } from '@forge/kvs';
import { validateIssueKey } from './jira.js';

const statuses = new Set(['accepted', 'superseded', 'proposed']);
function text(value, name, max, required = true) {
  if (value === undefined && !required) return '';
  if (typeof value !== 'string' || value.length > max || (required && !value.trim())) throw new Error(`Invalid ${name}`);
  return value.trim();
}
function key(id) {
  if (typeof id !== 'string' || !/^\d{13}-[a-f0-9-]{36}$/.test(id)) throw new Error('Invalid decision id');
  return `decision:${id}`;
}
export async function createDecision(input, authorAccountId) {
  if (!authorAccountId) throw new Error('Authenticated user required');
  const title = text(input.title, 'title', 120);
  const decision = text(input.decision, 'decision', 2000);
  const rationale = text(input.rationale, 'rationale', 2000, false);
  const status = input.status ?? 'accepted';
  if (!statuses.has(status) || status === 'superseded') throw new Error('Invalid initial status');
  const tags = input.tags ?? [];
  if (!Array.isArray(tags) || tags.length > 8) throw new Error('Invalid tags');
  const normalizedTags = [...new Set(tags.map(tag => text(tag, 'tag', 80).toLowerCase()))];
  if (input.issueKey) validateIssueKey(input.issueKey);
  if (input.projectKey && !/^[A-Z][A-Z0-9_]+$/.test(input.projectKey)) throw new Error('Invalid project key');
  const now = Date.now();
  const id = `${now}-${randomUUID()}`;
  const entry = { id, title, decision, rationale, status, tags: normalizedTags, authorAccountId, createdAt: new Date(now).toISOString(),
    ...(input.issueKey ? { issueKey: input.issueKey } : {}),
    ...(input.projectKey ? { projectKey: input.projectKey } : {}) };
  await kvs.set(key(id), entry);
  return entry;
}
export async function getDecision(id) { return kvs.get(key(id)); }
async function scanDecisions(max = 500) {
  const entries = [];
  let cursor;
  do {
    let query = kvs.query().where('key', WhereConditions.beginsWith('decision:')).limit(Math.min(100, max - entries.length));
    if (cursor) query = query.cursor(cursor);
    const result = await query.getMany();
    entries.push(...(result.results ?? []).map(row => row.value));
    cursor = result.nextCursor;
  } while (cursor && entries.length < max);
  return entries.slice(0, max).sort((a, b) => b.createdAt.localeCompare(a.createdAt) || b.id.localeCompare(a.id));
}
export async function listDecisions({ cursor, limit = 50 } = {}) {
  if (cursor && !/^offset:\d+$/.test(cursor)) throw new Error('Invalid cursor');
  const offset = cursor ? Number(cursor.slice(7)) : 0;
  const size = Math.min(100, Math.max(1, limit));
  const entries = await scanDecisions(Infinity);
  return { entries: entries.slice(offset, offset + size), cursor: offset + size < entries.length ? `offset:${offset + size}` : undefined };
}
export async function searchDecisions(query = '', filters = {}) {
  if (typeof query !== 'string' || query.length > 500) throw new Error('Invalid decision query');
  if (filters.status && !statuses.has(filters.status)) throw new Error('Invalid status');
  const entries = await scanDecisions();
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return entries.slice(0, 500).filter(entry => (!filters.status || entry.status === filters.status)
    && (!filters.projectKey || entry.projectKey === filters.projectKey)
    && (!filters.issueKey || entry.issueKey === filters.issueKey)
    && words.every(word => `${entry.title} ${entry.decision} ${entry.rationale} ${entry.tags.join(' ')} ${entry.issueKey ?? ''}`.toLowerCase().includes(word)))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || b.id.localeCompare(a.id));
}
export async function supersedeDecision(id, byId, authorAccountId) {
  if (id === byId) throw new Error('Replacement must be a different decision');
  const [entry, replacement] = await Promise.all([getDecision(id), getDecision(byId)]);
  if (!entry || !replacement) throw new Error('Decision not found');
  if (!authorAccountId || entry.authorAccountId !== authorAccountId) throw new Error('Only the author can supersede a decision');
  if (entry.status === 'superseded' || replacement.status !== 'accepted') throw new Error('Replacement must be accepted and original must not be superseded');
  const updated = { ...entry, status: 'superseded', supersededBy: byId };
  await kvs.set(key(id), updated);
  return updated;
}
