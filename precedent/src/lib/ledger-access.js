import { getIssue } from './jira.js';
import { createDecision, searchDecisions, getDecision, supersedeDecision } from './decisions.js';

export async function visibleDecisions(query = '', filters = {}) {
  const entries = await searchDecisions(query, filters);
  const access = new Map();
  for (const issueKey of new Set(entries.map(entry => entry.issueKey).filter(Boolean))) {
    try { await getIssue(issueKey); access.set(issueKey, true); } catch { access.set(issueKey, false); }
  }
  return entries.filter(entry => !entry.issueKey || access.get(entry.issueKey));
}
export async function recordDecision(input, context) {
  if (!context?.accountId) throw new Error('Authenticated user required');
  if (input.issueKey) await getIssue(input.issueKey);
  return createDecision({ ...input, projectKey: input.issueKey?.split('-')[0] ?? input.projectKey }, context.accountId);
}
export async function replaceDecision(id, byId, context) {
  const entries = await Promise.all([getDecision(id), getDecision(byId)]);
  for (const entry of entries) if (entry?.issueKey) await getIssue(entry.issueKey);
  return supersedeDecision(id, byId, context?.accountId);
}
