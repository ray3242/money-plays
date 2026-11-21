import Resolver from '@forge/resolver';
import { buildPrecedent } from './lib/precedent.js';
import { shipConfidence } from './lib/score.js';
import { validateIssueKey } from './lib/jira.js';
import { visibleDecisions, recordDecision, replaceDecision } from './lib/ledger-access.js';

export const definitions = {
  async getIssueContext({ context }) {
    const issueKey = validateIssueKey(context?.extension?.issue?.key);
    const precedent = await buildPrecedent(issueKey);
    return { ...precedent, confidence: shipConfidence(precedent.issue, precedent) };
  },
  async recordDecision({ payload, context }) {
    const issueKey = context?.extension?.issue?.key ?? payload?.issueKey;
    const projectKey = context?.extension?.project?.key ?? payload?.projectKey;
    if (projectKey !== undefined && (typeof projectKey !== 'string' || !/^[A-Z][A-Z0-9_]+$/.test(projectKey))) throw new Error('Invalid project key');
    return recordDecision({ ...payload, ...(issueKey ? { issueKey: validateIssueKey(issueKey) } : {}), ...(projectKey !== undefined ? { projectKey } : {}) }, context);
  },
  async supersedeDecision({ payload, context }) {
    return replaceDecision(payload?.id, payload?.byId, context);
  },
  async listDecisions({ payload = {}, context }) {
    if (!context?.accountId) throw new Error('Authenticated user required');
    const projectKey = context.extension?.project?.key ?? payload.projectKey;
    if (projectKey && !/^[A-Z][A-Z0-9_]+$/.test(projectKey)) throw new Error('Invalid project key');
    return { decisions: await visibleDecisions(payload.query ?? '', { status: payload.status, projectKey }) };
  }
};
const resolver = new Resolver();
for (const [name, fn] of Object.entries(definitions)) resolver.define(name, fn);
export const handler = resolver.getDefinitions();
