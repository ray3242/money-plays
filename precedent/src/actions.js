import { buildPrecedent } from './lib/precedent.js';
import { shipConfidence } from './lib/score.js';
import { validateIssueKey, issueUrl } from './lib/jira.js';
import { visibleDecisions, recordDecision } from './lib/ledger-access.js';

function issueKey(payload) { return validateIssueKey(payload?.issueKey ?? payload?.context?.jira?.issueKey); }
function compact(precedent) {
  return { issueKey: precedent.issue.key, url: issueUrl(precedent.issue.key), keywords: precedent.keywords,
    issues: precedent.issues.map(({ key, summary, url, kind, relevance }) => ({ key, summary, url, kind, relevance })),
    pages: precedent.pages, decisions: precedent.decisions.slice(0, 20).map(entry => ({ ...entry, ...(entry.issueKey ? { url: issueUrl(entry.issueKey) } : {}) })), people: precedent.people, graph: precedent.graph, warnings: precedent.warnings };
}
export async function getIssuePrecedent(payload) { return compact(await buildPrecedent(issueKey(payload))); }
export async function assessShipReadiness(payload) {
  const precedent = await buildPrecedent(issueKey(payload));
  return { issueKey: precedent.issue.key, url: issueUrl(precedent.issue.key), ...shipConfidence(precedent.issue, precedent), warnings: precedent.warnings };
}
export async function searchDecisionsAction(payload = {}) {
  return { decisions: (await visibleDecisions(payload.query ?? '', {})).slice(0, 30) };
}
export async function recordDecisionAction(payload = {}, context) {
  const linkedKey = payload.issueKey ?? payload.context?.jira?.issueKey;
  if (linkedKey) validateIssueKey(linkedKey);
  return recordDecision({ title: payload.title, decision: payload.decision, rationale: payload.rationale, ...(linkedKey ? { issueKey: linkedKey } : {}) }, context);
}
