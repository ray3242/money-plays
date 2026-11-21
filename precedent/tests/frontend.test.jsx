// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
const bridge = vi.hoisted(() => ({ initialize: vi.fn(), invoke: vi.fn() }));
vi.mock('../static/shared/bridge.js', () => ({ ...bridge, isMock: true, openLink: event => event.preventDefault() }));
vi.mock('@atlaskit/tokens', () => ({ token: (_, fallback) => fallback }));
import { App, DecisionForm } from '../static/shared/App.jsx';
const entry = { id: 'a', title: 'Reuse the payment key', decision: 'One key across retries.', rationale: 'Avoid double charges.', status: 'accepted', authorAccountId: 'ada', createdAt: '2026-11-18', tags: ['checkout'], issueKey: 'PAY-412' };
const precedent = { issue: { key: 'PAY-412', fields: { summary: 'Authorization retries' } }, confidence: { score: 72, grade: 'Caution', factors: [{ id: 'block', label: 'Unresolved blocker', impact: -15, evidence: 'Reconciliation incomplete', link: '/browse/PAY-398' }] }, issues: [], pages: [], decisions: [], people: [], warnings: ['Graph unavailable'], graph: { items: [] } };
beforeEach(() => {
  vi.resetAllMocks();
  bridge.initialize.mockResolvedValue({ accountId: 'ada', extension: { project: { key: 'PAY' } } });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);
it('validates required fields and issue key before invoking', async () => {
  render(<DecisionForm onSaved={vi.fn()} onCancel={vi.fn()} />);
  fireEvent.submit(screen.getByRole('form'));
  expect(screen.getAllByText('Add this before recording the decision.')).toHaveLength(3);
  expect(bridge.invoke).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'Use a key' } });
  fireEvent.change(screen.getByLabelText(/^Decision/), { target: { value: 'Reuse the original' } });
  fireEvent.change(screen.getByLabelText(/Rationale/), { target: { value: 'Prevent duplicates' } });
  fireEvent.change(screen.getByLabelText(/Linked issue/), { target: { value: 'bad' } });
  fireEvent.submit(screen.getByRole('form'));
  expect(screen.getByText('Use an issue key such as PAY-412.')).toBeTruthy();
});
it('saves confirmed form values and renders a non-destructive failure', async () => {
  const onSaved = vi.fn();
  bridge.invoke.mockRejectedValueOnce(new Error('403')).mockResolvedValueOnce(entry);
  render(<DecisionForm issueKey="PAY-412" onSaved={onSaved} onCancel={vi.fn()} />);
  for (const [label, value] of [[/Title/, 'Use a key'], [/^Decision/, 'Reuse the original'], [/Rationale/, 'Prevent duplicates']]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fireEvent.submit(screen.getByRole('form'));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'The decision wasn’t saved. Check your access and try again.');
  expect(screen.getByLabelText(/Title/).value).toBe('Use a key');
  fireEvent.submit(screen.getByRole('form'));
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(entry));
  expect(bridge.invoke).toHaveBeenLastCalledWith('recordDecision', { title: 'Use a key', decision: 'Reuse the original', rationale: 'Prevent duplicates', issueKey: 'PAY-412' });
});
it('renders panel score, empty states, expandable evidence and tabs', async () => {
  bridge.invoke.mockResolvedValue(precedent);
  render(<App surface="panel" />);
  expect(screen.getByRole('status')).toBeTruthy();
  expect(await screen.findByText('Authorization retries')).toBeTruthy();
  expect(screen.getByRole('img', { name: '72 out of 100. Caution' })).toBeTruthy();
  expect(screen.getByText('No close precedents yet')).toBeTruthy();
  fireEvent.click(screen.getByText('Unresolved blocker'));
  expect(screen.getByText('Reconciliation incomplete')).toBeTruthy();
  fireEvent.click(screen.getByRole('tab', { name: /People/ }));
  expect(screen.getByText('No context holders found')).toBeTruthy();
  fireEvent.click(screen.getByRole('tab', { name: /Decisions/ }));
  expect(screen.getByText('Make the first decision visible')).toBeTruthy();
});
it('allows retry after a loading error', async () => {
  bridge.invoke.mockRejectedValueOnce(new Error('503')).mockResolvedValueOnce(precedent);
  render(<App surface="panel" />);
  expect(await screen.findByText('Context couldn’t be loaded')).toBeTruthy();
  fireEvent.click(screen.getByText('Try again'));
  expect(await screen.findByText('Authorization retries')).toBeTruthy();
});
it('filters ledger on the server and lets only the author supersede', async () => {
  const other = { ...entry, id: 'b', title: 'Reconcile first', authorAccountId: 'marcus' };
  bridge.invoke.mockResolvedValue({ decisions: [entry, other] });
  render(<App surface="ledger" />);
  await screen.findByText('2 decisions on record');
  fireEvent.click(screen.getByRole('button', { name: 'Supersede decision' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'b' } });
  bridge.invoke.mockResolvedValueOnce({ ...entry, status: 'superseded', supersededBy: 'b' });
  fireEvent.click(screen.getByText('Confirm replacement'));
  await waitFor(() => expect(bridge.invoke).toHaveBeenCalledWith('supersedeDecision', { id: 'a', byId: 'b' }));
  fireEvent.click(screen.getByRole('button', { name: /Reconcile first/ }));
  expect(screen.getByText('Only the author can supersede this decision.')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Supersede decision' })).toBeNull();
  fireEvent.change(screen.getByRole('textbox', { name: 'Search decisions' }), { target: { value: 'queue' } });
  await waitFor(() => expect(bridge.invoke).toHaveBeenCalledWith('listDecisions', { query: 'queue', status: undefined }));
  fireEvent.click(screen.getByRole('button', { name: 'proposed' }));
  await waitFor(() => expect(bridge.invoke).toHaveBeenCalledWith('listDecisions', { query: 'queue', status: 'proposed' }));
});
