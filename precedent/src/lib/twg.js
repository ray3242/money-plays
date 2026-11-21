import api from '@forge/api';

// Curated query: https://developer.atlassian.com/platform/teamwork-graph/curated-queries/
export async function relatedWork(issue) {
  const accountId = issue.fields?.assignee?.accountId;
  if (!accountId) return { items: [], note: 'Teamwork Graph skipped: no assignee.' };
  try {
    const response = await api.asUser().requestTeamworkGraph(`
      query precedent_assignedWork($userId: ID!) {
        atlassianUserAssignedJiraWorkItems(userId: $userId, first: 25) {
          edges { node { ... on JiraWorkItem { id title } } }
        }
      }`, { userId: `ari:cloud:identity::user/${accountId}` });
    if (!response.ok) throw new Error('Graph unavailable');
    const data = await response.json();
    if (data.errors?.length) throw new Error('Graph query denied');
    const items = (data.data?.atlassianUserAssignedJiraWorkItems?.edges ?? []).map(edge => edge.node).filter(Boolean);
    return items.length ? { items } : { items: [], note: 'Teamwork Graph skipped: no visible results (scope grants may be missing).' };
  } catch {
    return { items: [], note: 'Teamwork Graph enrichment unavailable; Jira and ledger evidence are unaffected.' };
  }
}
