const seed = [
  { id: 'decision-1', title: 'Use one idempotency key across authorization retries', decision: 'Generate the idempotency key at checkout creation. Reuse it for every authorization attempt, including after a timeout. Never retry with a new key.', rationale: 'A timeout is not a failed authorization. PAY-286 showed that a second key can create a second charge while the original request is still processing.', status: 'accepted', issueKey: 'PAY-412', projectKey: 'PAY', tags: ['checkout', 'idempotency'], authorAccountId: 'ada', createdAt: '2026-11-18T10:30:00Z' },
  { id: 'decision-2', title: 'Cap automatic retries at two attempts', decision: 'Allow two retries with exponential backoff. Reconcile with the gateway before presenting a final payment failure.', rationale: 'Limits pressure on the payment gateway while giving slow authorizations time to settle.', status: 'proposed', issueKey: 'PAY-412', projectKey: 'PAY', tags: ['resilience', 'gateway'], authorAccountId: 'marcus', createdAt: '2026-11-17T14:00:00Z' },
  { id: 'decision-3', title: 'Retry timeouts with a new authorization request', decision: 'Create a fresh authorization when the gateway does not respond in five seconds.', rationale: 'Originally chosen to reduce checkout abandonment. Replaced after the double-charge incident.', status: 'superseded', supersededBy: 'decision-1', issueKey: 'PAY-286', projectKey: 'PAY', tags: ['checkout'], authorAccountId: 'ada', createdAt: '2026-10-08T09:00:00Z' },
  { id: 'decision-4', title: 'Keep a 24-hour authorization reconciliation window', decision: 'Reconcile timed-out authorizations against gateway settlement events for 24 hours.', rationale: 'Some gateway callbacks arrive after the checkout session has ended.', status: 'accepted', issueKey: 'PAY-358', projectKey: 'PAY', tags: ['reconciliation'], authorAccountId: 'ada', createdAt: '2026-10-28T11:00:00Z' }
];
seed.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
let decisions;
try { decisions = JSON.parse(localStorage.getItem('precedent-demo-decisions')) ?? structuredClone(seed); } catch { decisions = structuredClone(seed); }
const persist = () => localStorage.setItem('precedent-demo-decisions', JSON.stringify(decisions));
export async function invoke(name, payload = {}) {
  await new Promise(resolve => setTimeout(resolve, 300));
  const state = new URLSearchParams(location.search).get('state');
  if (state === 'error') throw new Error('We couldn’t reach Jira. Your decisions are safe. Try again in a moment.');
  if (name === 'recordDecision') {
    const entry = { ...payload, id: `demo-${Date.now()}`, issueKey: payload.issueKey || undefined, projectKey: 'PAY', authorAccountId: 'ada', status: 'accepted', createdAt: new Date().toISOString(), tags: payload.tags ?? [] };
    decisions.unshift(entry); persist(); return entry;
  }
  if (name === 'supersedeDecision') {
    const entry = decisions.find(item => item.id === payload.id);
    if (entry.authorAccountId !== 'ada') throw new Error('Only the author can supersede a decision.');
    entry.status = 'superseded'; entry.supersededBy = payload.byId; persist(); return entry;
  }
  if (name === 'listDecisions') return { decisions: state === 'empty' ? [] : decisions.filter(entry => (!payload.status || entry.status === payload.status) && `${entry.title} ${entry.decision} ${entry.tags.join(' ')}`.toLowerCase().includes((payload.query ?? '').toLowerCase())) };
  return {
    issue: { key: 'PAY-412', fields: { summary: 'Enable retry on card authorization timeouts', status: { name: 'In review' }, assignee: { accountId: 'ada' } } },
    keywords: ['authorization', 'retry', 'timeouts', 'checkout', 'gateway', 'idempotency'],
    confidence: { score: 72, grade: 'Caution', factors: [
      { id: 'blockers', label: 'Gateway reconciliation is still blocking', impact: -15, evidence: 'PAY-398 must reconcile pending authorizations before retries can be enabled.', link: '/browse/PAY-398' },
      { id: 'past-incidents', label: 'Three similar changes led to incidents', impact: -18, evidence: 'PAY-286, PAY-331 and PAY-358 share authorization and retry keywords. Review the failure modes below.', link: '/browse/PAY-286' },
      { id: 'accepted', label: 'An accepted decision covers this change', impact: 5, evidence: 'The team agreed to reuse the same idempotency key on every retry.', link: '/browse/PAY-412' }
    ] },
    issues: state === 'empty' ? [] : [
      { key: 'PAY-286', summary: 'Double charges after authorization timeout retry', kind: 'incident', relevance: 5, url: '/browse/PAY-286', resolvedAt: '2026-10-14T12:00:00Z' },
      { key: 'PAY-331', summary: 'Retry storm exhausted the gateway connection pool', kind: 'incident', relevance: 4, url: '/browse/PAY-331', resolvedAt: '2026-10-27T12:00:00Z' },
      { key: 'PAY-358', summary: 'Reconcile delayed payment authorization callbacks', kind: 'bug', relevance: 3, url: '/browse/PAY-358', resolvedAt: '2026-11-04T12:00:00Z' }
    ],
    pages: state === 'empty' ? [] : [{ id: 'page-7', title: 'ADR-007 · Idempotency keys for payment retries', url: '/wiki/spaces/PAY/pages/7', excerpt: 'One checkout, one key. Reuse the original idempotency key until the authorization reaches a final state.', lastModified: '2026-11-18T10:00:00Z' }],
    decisions: state === 'empty' ? [] : decisions.filter(entry => entry.issueKey === 'PAY-412'),
    people: state === 'empty' ? [] : [{ accountId: 'marcus', displayName: 'Marcus Chen', count: 2, issueKeys: ['PAY-286', 'PAY-331'] }, { accountId: 'ada', displayName: 'Ada Williams', count: 1, issueKeys: ['PAY-358'] }],
    graph: { items: [] }, warnings: ['Teamwork Graph is unavailable. Jira and decision evidence are still included.']
  };
}
