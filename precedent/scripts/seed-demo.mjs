import { pathToFileURL } from 'node:url';

export function buildPlan({ PROJECT_KEY = 'PAY', SPACE_KEY = 'PAY' } = {}) {
  if (!/^[A-Z][A-Z0-9_]+$/.test(PROJECT_KEY)) throw new Error('PROJECT_KEY must be an uppercase Jira project key.');
  if (!/^[A-Za-z0-9]+$/.test(SPACE_KEY)) throw new Error('SPACE_KEY must contain letters and numbers only.');
  const shared = 'Enable card authorization retry timeouts checkout gateway idempotency. ';
  return {
    projectKey: PROJECT_KEY, spaceKey: SPACE_KEY,
    issues: [
      { id: 'double-charge', summary: 'Double charges after authorization timeout retry', type: 'Bug', labels: ['incident', 'checkout'], resolved: true, description: shared + 'A fresh key on a retry produced a second charge. Reuse the original idempotency key. Acceptance criteria: duplicate authorization requests produce one charge.' },
      { id: 'retry-storm', summary: 'Retry storm exhausted the gateway connection pool', type: 'Bug', labels: ['incident', 'gateway'], resolved: true, description: shared + 'Unbounded retries exhausted connections. Acceptance criteria: cap retries at two with exponential backoff.' },
      { id: 'callbacks', summary: 'Reconcile delayed payment authorization callbacks', type: 'Bug', labels: ['checkout'], resolved: true, description: shared + 'Delayed callbacks arrived after checkout ended. Acceptance criteria: reconcile pending authorizations for 24 hours.' },
      { id: 'blocker', summary: 'Reconcile pending authorizations before enabling retries', type: 'Task', labels: ['gateway'], resolved: false, description: shared + 'Gateway reconciliation is still blocking rollout. Acceptance criteria: match pending requests against settlement events.' },
      { id: 'target', summary: 'Enable retry on card authorization timeouts', type: 'Task', labels: ['checkout', 'idempotency'], resolved: false, description: shared + 'Retry card authorization timeouts without creating duplicate charges. Reuse the checkout idempotency key. Acceptance criteria: at most two retries; reconcile the gateway before final failure; do not ship until the linked blocker is resolved.' }
    ],
    link: { type: 'Blocks', from: 'blocker', to: 'target' },
    pages: [
      { title: 'ADR-007 · Idempotency keys for payment retries', labels: ['decision', 'adr'], text: shared + 'One checkout, one key. Reuse the original idempotency key until authorization reaches a final state. A timeout is not a failed authorization. This decision applies to {{target}} and follows the double-charge incident {{double-charge}}.' },
      { title: 'Decision · Payment retry limits and reconciliation', labels: ['decision'], text: shared + 'Cap automatic retries at two attempts with exponential backoff. Keep a 24-hour reconciliation window for delayed callbacks. Resolve {{blocker}} before shipping {{target}}.' }
    ]
  };
}

export function doneTransition(transitions) {
  const transition = transitions.find(item => item.to?.statusCategory?.key === 'done');
  if (!transition) throw new Error('No available transition leads to status category done. Configure a direct Done transition and rerun.');
  return transition;
}

export async function seed(plan, { site, email, token, fetcher = fetch, log = console.log }) {
  const origin = new URL(site);
  if (origin.protocol !== 'https:' || !origin.hostname.endsWith('.atlassian.net') || origin.pathname !== '/' || origin.username || origin.password || origin.search || origin.hash || origin.port) throw new Error('ATLASSIAN_SITE must be an HTTPS https://your-site.atlassian.net origin.');
  if (!email || !token) throw new Error('ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN are required.');
  async function request(path, method = 'GET', body, allowed = []) {
    const response = await fetcher(new URL(path, origin), { method, redirect: 'error', headers: { Authorization: `Basic ${Buffer.from(`${email}:${token}`).toString('base64')}`, Accept: 'application/json', 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) });
    if (allowed.includes(response.status)) return null;
    if (!response.ok) throw new Error(`${method} ${path.split('?')[0]} failed (${response.status}). Check admin permissions, token access and workflow required fields; no response body or credentials logged.`);
    if (response.status === 204) return null;
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }
  const projectPath = `/rest/api/3/project/${encodeURIComponent(plan.projectKey)}`;
  let project = await request(projectPath, 'GET', undefined, [404]);
  const me = await request('/rest/api/3/myself');
  if (!project) {
    project = await request('/rest/api/3/project', 'POST', { key: plan.projectKey, name: `${plan.projectKey} Payments demo`, projectTypeKey: 'software', projectTemplateKey: 'com.pyxis.greenhopper.jira:gh-simplified-scrum-classic', leadAccountId: me.accountId });
    log(`Created project ${plan.projectKey}`);
  }
  const metadata = await request(projectPath);
  const adf = text => ({ type: 'doc', version: 1, content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });
  const keys = {};
  for (const item of plan.issues) {
    const phrase = item.summary.split(' ').slice(0, 3).join(' ');
    let matches = [], nextPageToken;
    do {
      const result = await request('/rest/api/3/search/jql', 'POST', { jql: `project = "${plan.projectKey}" AND summary ~ "${phrase}"`, fields: ['summary'], maxResults: 100, ...(nextPageToken ? { nextPageToken } : {}) });
      matches.push(...result.issues); nextPageToken = result.isLast === true ? undefined : result.nextPageToken;
    } while (nextPageToken);
    let issue = matches.find(found => found.fields.summary === item.summary);
    if (!issue) {
      const type = metadata.issueTypes?.find(type => type.name.toLowerCase() === item.type.toLowerCase() && !type.subtask);
      if (!type) throw new Error(`Project needs a ${item.type} issue type. Add it and rerun.`);
      issue = await request('/rest/api/3/issue', 'POST', { fields: { project: { key: plan.projectKey }, issuetype: { id: type.id }, summary: item.summary, description: adf(item.description), labels: [...item.labels, 'precedent-demo'], assignee: { accountId: me.accountId } } });
      log(`Created ${issue.key}: ${item.summary}`);
    } else log(`Using ${issue.key}: ${item.summary}`);
    keys[item.id] = issue.key;
    if (item.resolved) {
      let current = await request(`/rest/api/3/issue/${issue.key}?fields=status,resolution`);
      if (current.fields.status.statusCategory.key !== 'done') {
        const result = await request(`/rest/api/3/issue/${issue.key}/transitions?expand=transitions.fields`);
        for (const transition of result.transitions) {
          if (!transition.to?.statusCategory && transition.to?.id) transition.to.statusCategory = (await request(`/rest/api/3/status/${encodeURIComponent(transition.to.id)}`)).statusCategory;
        }
        const transition = doneTransition(result.transitions);
        const body = { transition: { id: transition.id } };
        if (transition.fields?.resolution) {
          const choices = transition.fields.resolution.allowedValues ?? await request('/rest/api/3/resolution');
          const resolution = choices.find(value => /^(done|fixed)$/i.test(value.name)) ?? choices[0];
          if (!resolution) throw new Error('No resolution is configured. Configure a Fixed resolution and rerun.');
          body.fields = { resolution: { id: resolution.id } };
        }
        await request(`/rest/api/3/issue/${issue.key}/transitions`, 'POST', body);
        current = await request(`/rest/api/3/issue/${issue.key}?fields=status,resolution`);
      }
      if (current.fields.status.statusCategory.key !== 'done' || !current.fields.resolution) throw new Error(`${issue.key} must have a Done status AND a resolution. Configure the workflow to set resolution on Done, fix this issue, and rerun.`);
    }
  }
  const target = await request(`/rest/api/3/issue/${keys.target}?fields=issuelinks`);
  const linkTypes = await request('/rest/api/3/issueLinkType');
  const linkType = linkTypes.issueLinkTypes.find(type => /^blocks$/i.test(type.outward) && /^is blocked by$/i.test(type.inward));
  if (!linkType) throw new Error('Configure a Blocks / is blocked by issue link type and rerun.');
  if (!target.fields.issuelinks?.some(link => link.inwardIssue?.key === keys.blocker && link.type.id === linkType.id)) await request('/rest/api/3/issueLink', 'POST', { type: { id: linkType.id }, inwardIssue: { key: keys.blocker }, outwardIssue: { key: keys.target } });
  let space = await request(`/wiki/rest/api/space/${encodeURIComponent(plan.spaceKey)}`, 'GET', undefined, [404]);
  if (!space) space = await request('/wiki/rest/api/space', 'POST', { key: plan.spaceKey, name: `${plan.projectKey} Payments decisions` });
  for (const page of plan.pages) {
    const result = await request(`/wiki/rest/api/content?type=page&spaceKey=${encodeURIComponent(plan.spaceKey)}&title=${encodeURIComponent(page.title)}&limit=100`);
    let content = result.results.find(item => item.title === page.title);
    if (!content) {
      const text = page.text.replace(/\{\{([^}]+)\}\}/g, (_, id) => keys[id]).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
      content = await request('/wiki/rest/api/content', 'POST', { type: 'page', title: page.title, space: { key: plan.spaceKey }, body: { storage: { value: `<p>${text}</p>`, representation: 'storage' } } });
      log(`Created page: ${page.title}`);
    } else log(`Using page: ${page.title}`);
    await request(`/wiki/rest/api/content/${content.id}/label`, 'POST', page.labels.map(name => ({ prefix: 'global', name })));
  }
  log(`Open ${origin.origin}/browse/${keys.target}`);
  log('Issue numbers are allocated by Jira, not forced to PAY-412. Record the accepted idempotency decision in Precedent to complete the ledger story (expected score: 72).');
  return keys;
}

export async function main(args = process.argv.slice(2), env = process.env) {
  if (args.some(arg => arg !== '--dry-run')) throw new Error('Usage: node scripts/seed-demo.mjs [--dry-run]');
  const plan = buildPlan(env);
  if (args.includes('--dry-run')) { console.log('DRY RUN: no network requests; no credentials required.'); console.log(JSON.stringify(plan, null, 2)); return; }
  if (!env.ATLASSIAN_SITE) throw new Error('Set ATLASSIAN_SITE, ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN. Use --dry-run for an offline plan.');
  await seed(plan, { site: env.ATLASSIAN_SITE, email: env.ATLASSIAN_EMAIL, token: env.ATLASSIAN_API_TOKEN });
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main().catch(error => { console.error(error.message); process.exitCode = 1; });
