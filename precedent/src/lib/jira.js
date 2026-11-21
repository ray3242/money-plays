import api, { route } from '@forge/api';

export const ISSUE_KEY = /^[A-Z][A-Z0-9_]+-\d+$/;
export function validateIssueKey(key) {
  if (typeof key !== 'string' || !ISSUE_KEY.test(key)) throw new Error('Invalid issue key');
  return key;
}
export const issueFields = ['summary', 'description', 'status', 'statuscategory', 'issuetype', 'priority', 'labels', 'components', 'assignee', 'resolution', 'resolutiondate', 'issuelinks', 'created', 'updated'];
export async function getIssue(key) {
  validateIssueKey(key);
  const response = await api.asUser().requestJira(route`/rest/api/3/issue/${key}?fields=${issueFields.join(',')}&expand=changelog`);
  if (!response.ok) throw new Error(`Issue unavailable (${response.status})`);
  const issue = await response.json();
  try {
    const statuses = await api.asUser().requestJira(route`/rest/api/3/project/${key.split('-')[0]}/statuses`);
    if (!statuses.ok) throw new Error('Status categories unavailable');
    issue.statusCategories = Object.fromEntries((await statuses.json()).flatMap(type => type.statuses ?? []).map(status => [status.id, status.statusCategory?.key]));
  } catch { issue.statusCategoryWarning = 'Historical status categories unavailable; reopen detection falls back to standard status names.'; }
  return issue;
}
export async function searchJql(jql, fields = issueFields, max = 8) {
  const response = await api.asUser().requestJira(route`/rest/api/3/search/jql`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ jql, fields, maxResults: Math.min(100, Math.max(1, max)) })
  });
  if (!response.ok) throw new Error(`Jira search unavailable (${response.status})`);
  return (await response.json()).issues ?? [];
}
export function issueUrl(key) { return `/browse/${encodeURIComponent(key)}`; }
