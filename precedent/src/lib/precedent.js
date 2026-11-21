import { getIssue, searchJql, issueUrl } from './jira.js';
import { searchCql } from './confluence.js';
import { extractKeywords, normalizeText, safePhrase } from './keywords.js';
import { adfToText } from './adf.js';
import { visibleDecisions } from './ledger-access.js';
import { relatedWork } from './twg.js';

export function precedentKind(issue) {
  const labels = issue.fields?.labels ?? [];
  if (labels.some(label => /^(revert|rollback)$/i.test(label))) return 'revert';
  if (labels.some(label => /^(incident|hotfix|regression)$/i.test(label))) return 'incident';
  return issue.fields?.issuetype?.name?.toLowerCase() === 'bug' ? 'bug' : 'work';
}
export async function buildPrecedent(issueKey) {
  const issue = await getIssue(issueKey);
  const keywords = extractKeywords(issue);
  const projectKey = issueKey.split('-')[0];
  const warnings = [];
  if ((issue.changelog?.total ?? 0) > (issue.changelog?.histories?.length ?? 0)) warnings.push('Jira changelog is partial; reopen counts may be understated.');
  if (issue.statusCategoryWarning) warnings.push(issue.statusCategoryWarning);
  const terms = keywords.map(term => `text ~ "${safePhrase(term)}"`).join(' OR ');
  const rawIssues = terms ? await searchJql(`project = "${projectKey}" AND resolution IS NOT EMPTY AND key != "${issueKey}" AND (${terms}) ORDER BY resolved DESC`, undefined, 8) : [];
  const issues = rawIssues.map(item => {
    const text = normalizeText(`${item.fields?.summary ?? ''} ${adfToText(item.fields?.description)} ${(item.fields?.labels ?? []).join(' ')}`);
    const words = new Set(text.split(' '));
    return { key: item.key, summary: item.fields?.summary, kind: precedentKind(item), relevance: keywords.filter(word => words.has(word)).length,
      url: issueUrl(item.key), assignee: item.fields?.assignee, resolvedAt: item.fields?.resolutiondate };
  }).sort((a, b) => b.relevance - a.relevance);
  let pages = [];
  if (keywords.length) {
    try {
      const phrase = safePhrase(keywords.join(' '));
      pages = await searchCql(`type = page AND (label IN ("decision", "adr", "decision-record") OR title ~ "decision" OR title ~ "ADR") AND text ~ "${phrase}"`, 6);
    } catch { warnings.push('Confluence decision search unavailable; check installation and permissions.'); }
  }
  const candidates = (await visibleDecisions('', {})).filter(entry => !entry.projectKey || entry.projectKey === projectKey);
  const components = (issue.fields?.components ?? []).map(component => component.name.toLowerCase());
  const decisions = candidates.filter(entry => entry.issueKey === issueKey || entry.tags.some(tag => components.includes(tag.toLowerCase()))
    || keywords.some(word => `${entry.title} ${entry.decision} ${entry.tags.join(' ')}`.toLowerCase().includes(word)));
  const people = new Map();
  for (const item of issues) {
    if (!item.assignee?.accountId) continue;
    const existing = people.get(item.assignee.accountId) ?? { accountId: item.assignee.accountId, displayName: item.assignee.displayName, count: 0, issueKeys: [] };
    existing.count += 1;
    existing.issueKeys.push(item.key);
    people.set(existing.accountId, existing);
  }
  const graph = await relatedWork(issue);
  if (graph.note) warnings.push(graph.note);
  if (!keywords.length) warnings.push('No useful keywords found; text searches skipped.');
  return { issue, keywords, issues, pages, decisions, people: [...people.values()].sort((a, b) => b.count - a.count || a.accountId.localeCompare(b.accountId)), graph, warnings };
}
