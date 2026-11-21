import { adfToText } from './adf.js';

const done = fields => Boolean(fields?.resolution) || fields?.status?.statusCategory?.key === 'done';
export function shipConfidence(issue, precedent = {}) {
  const factors = [];
  const add = (id, label, impact, evidence, link) => { if (impact) factors.push({ id, label, impact, evidence, ...(link ? { link } : {}) }); };
  const links = issue.fields?.issuelinks ?? [];
  const blockers = links.filter(link => link.inwardIssue && /is blocked by/i.test(link.type?.inward ?? '') && !done(link.inwardIssue.fields));
  const bugs = links.map(link => link.inwardIssue ?? link.outwardIssue).filter(linked => linked?.fields?.issuetype?.name?.toLowerCase() === 'bug' && !done(linked.fields));
  add('blockers', 'Unresolved blockers', -Math.min(30, blockers.length * 15), blockers.map(link => link.inwardIssue.key).join(', '));
  add('linked-bugs', 'Unresolved linked bugs', -Math.min(24, bugs.length * 8), bugs.map(link => link.key).join(', '));
  const histories = issue.changelog?.histories ?? [];
  const completed = (item, side) => {
    const category = item[`${side}StatusCategory`]?.key ?? issue.statusCategories?.[item[side]];
    return category ? category === 'done' : /^(done|closed|resolved)$/i.test(item[`${side}String`] ?? '');
  };
  const reopenCount = histories.flatMap(history => history.items ?? []).filter(item => item.field === 'status' && completed(item, 'from') && !completed(item, 'to')).length;
  add('reopened', 'Reopened after completion', -Math.min(20, reopenCount * 10), `${reopenCount} completed-to-active transitions in available changelog`);
  const description = adfToText(issue.fields?.description);
  if (description.length < 40 || !/acceptance criteria|\bAC\s*:|given[\s\S]*when[\s\S]*then|\[[ xX]\]/i.test(description)) add('description', 'Acceptance criteria missing or description short', -10, 'Add a clear description and acceptance criteria.');
  const incidents = (precedent.issues ?? []).filter(item => ['bug', 'incident', 'revert'].includes(item.kind));
  add('past-incidents', 'Past failures in similar work', -Math.min(18, incidents.length * 6), incidents.map(item => item.key).join(', '));
  const decisions = precedent.decisions ?? [];
  const referenced = decisions.filter(entry => entry.issueKey === issue.key);
  if (referenced.some(entry => entry.status === 'superseded')) add('superseded', 'Referenced decision superseded', -5, 'Review the replacement decision before shipping.');
  if (referenced.some(entry => entry.status === 'accepted')) add('accepted', 'Accepted decision linked', 5, 'An accepted decision is recorded for this issue.', `/browse/${encodeURIComponent(issue.key)}`);
  const score = Math.min(100, Math.max(0, 100 + factors.reduce((sum, factor) => sum + factor.impact, 0)));
  return { score, grade: score >= 80 ? 'Ready' : score >= 55 ? 'Caution' : 'At risk', factors };
}
