import { describe, it, expect } from 'vitest';
import { adfToText } from '../src/lib/adf.js';
import { safePhrase, extractKeywords } from '../src/lib/keywords.js';
import { shipConfidence } from '../src/lib/score.js';

const issue = () => ({ key: 'APP-1', fields: { description: 'Acceptance criteria: given a valid request when submitted then the operation succeeds.', issuelinks: [] } });
describe('ADF', () => {
  it('handles nested text, breaks, mention and card', () => {
    expect(adfToText({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi ' }, { type: 'mention', attrs: { text: '@Ada' } }, { type: 'hardBreak' }, { type: 'inlineCard', attrs: { url: 'https://example.com' } }] }] })).toBe('Hi @Ada\nhttps://example.com');
  });
  it('handles empty, unknown and caps output', () => {
    expect(adfToText(null)).toBe('');
    expect(adfToText({ type: 'unknown' })).toBe('');
    expect(adfToText({ type: 'text', text: 'abcdef' }, 3)).toBe('abc');
    expect(adfToText('plain')).toBe('plain');
  });
  it('preserves ADF checklist markers', () => {
    expect(adfToText({ type: 'taskItem', attrs: { state: 'DONE' }, content: [{ type: 'text', text: 'Tests pass' }] })).toBe('[x] Tests pass');
  });
});
describe('keywords', () => {
  it('weights summary x3, filters filler, uses labels/components and deterministic ties', () => {
    expect(extractKeywords({ fields: { summary: 'Jira payment ticket', description: 'cache cache', labels: ['latency'], components: [{ name: 'Gateway' }] } })).toEqual(['payment', 'cache', 'gateway', 'latency']);
    expect(extractKeywords({ summary: 'beta alpha' }, 1)).toEqual(['alpha']);
  });
  it('handles empty input and removes query operators and quoting', () => {
    expect(extractKeywords(null)).toEqual([]);
    expect(safePhrase('a"\\ OR (x:y) +z*?')).toBe('a or x y z');
    expect(safePhrase(null)).toBe('');
  });
});
describe('ship confidence', () => {
  it('starts ready, clamps bonus at 100 and requires linked accepted decisions', () => {
    expect(shipConfidence(issue()).score).toBe(100);
    const result = shipConfidence(issue(), { decisions: [{ status: 'accepted', issueKey: 'APP-1' }] });
    expect(result).toMatchObject({ score: 100, grade: 'Ready' });
    expect(result.factors[0].impact).toBe(5);
  });
  it('caps blockers, linked bugs, reopens, failures; clamps zero', () => {
    const input = issue();
    input.fields.description = '';
    input.fields.issuelinks = Array.from({ length: 5 }, (_, i) => ({ type: { inward: 'is blocked by' }, inwardIssue: { key: `APP-${i+2}`, fields: { issuetype: { name: 'Bug' } } } }));
    input.changelog = { histories: [{ items: Array.from({ length: 4 }, () => ({ field: 'status', fromString: 'Done', toString: 'In Progress' })) }] };
    const result = shipConfidence(input, { issues: Array.from({ length: 5 }, () => ({ key: 'APP-8', kind: 'incident' })), decisions: [{ issueKey: 'APP-1', status: 'superseded' }] });
    expect(result).toMatchObject({ score: 0, grade: 'At risk' });
    expect(result.factors.map(f => f.impact)).toEqual([-30, -24, -20, -10, -18, -5]);
  });
  it('ignores resolved links, outward blocks and unrelated decisions', () => {
    const input = issue();
    input.fields.issuelinks = [{ type: { outward: 'blocks' }, outwardIssue: { fields: { resolution: { name: 'Fixed' }, issuetype: { name: 'Bug' } } } }, { type: { inward: 'is blocked by' }, inwardIssue: { fields: { status: { statusCategory: { key: 'done' } } } } }];
    expect(shipConfidence(input, { decisions: [{ issueKey: 'OTHER-1', status: 'superseded' }] }).factors).toEqual([]);
  });
  it('counts each unresolved linked bug once across link types and directions', () => {
    const input = issue();
    const bug = { key: 'APP-2', fields: { issuetype: { name: 'Bug' } } };
    input.fields.issuelinks = [
      { type: { outward: 'relates to' }, outwardIssue: bug },
      { type: { inward: 'is duplicated by' }, inwardIssue: { ...bug } },
      { type: { outward: 'blocks' }, outwardIssue: { ...bug } },
      { outwardIssue: { ...bug, key: 'APP-3', fields: { ...bug.fields, resolution: { name: 'Fixed' } } } }
    ];
    expect(shipConfidence(input)).toMatchObject({ score: 92, factors: [{ id: 'linked-bugs', impact: -8, evidence: 'APP-2' }] });
    input.fields.issuelinks.push({ inwardIssue: { ...bug, key: 'APP-4' } });
    expect(shipConfidence(input)).toMatchObject({ score: 84, factors: [{ id: 'linked-bugs', impact: -16, evidence: 'APP-2, APP-4' }] });
  });
  it('detects custom Done-category transitions without counting done-to-done', () => {
    const input = issue();
    input.statusCategories = { 1: 'done', 2: 'indeterminate', 3: 'done' };
    input.changelog = { histories: [{ items: [{ field: 'status', from: '1', to: '2', fromString: 'Shipped' }, { field: 'status', from: '1', to: '3' }, { field: 'priority', fromString: 'Done' }] }] };
    expect(shipConfidence(input).score).toBe(90);
  });
  it.each(['AC: all checks pass and this description is long enough to be useful', 'given a valid user when saving then the record persists as expected', '[ ] tests cover all failure scenarios and meet the release requirements'])('accepts criteria marker %s', description => {
    const input = issue(); input.fields.description = description;
    expect(shipConfidence(input).score).toBe(100);
  });
  it('grades at boundaries', () => {
    const input = issue();
    input.fields.issuelinks = [{ type: { inward: 'is blocked by' }, inwardIssue: { key: 'APP-2', fields: {} } }];
    expect(shipConfidence(input, { issues: [{ kind: 'bug' }] }).grade).toBe('Caution');
    expect(shipConfidence(input, { issues: [{ kind: 'bug' }, { kind: 'bug' }, { kind: 'bug' }] }).score).toBe(67);
  });
  it('implements exact grade cutoffs and metadata takes precedence over names', () => {
    const input = issue();
    input.changelog = { histories: [{ items: [{ field: 'status', fromString: 'Done', toString: 'Active' }, { field: 'status', fromString: 'Done', toString: 'Active' }] }] };
    expect(shipConfidence(input)).toMatchObject({ score: 80, grade: 'Ready' });
    input.fields.issuelinks = [{ type: { inward: 'is blocked by' }, inwardIssue: { key: 'APP-2', fields: {} } }];
    input.fields.description = '';
    expect(shipConfidence(input)).toMatchObject({ score: 55, grade: 'Caution' });
    expect(shipConfidence(input, { issues: [{ kind: 'bug' }] })).toMatchObject({ score: 49, grade: 'At risk' });
    input.changelog.histories[0].items = [{ field: 'status', from: '1', fromString: 'Done', toString: 'Active' }];
    input.statusCategories = { 1: 'indeterminate' };
    expect(shipConfidence(input).factors.find(f => f.id === 'reopened')).toBeUndefined();
  });
});
