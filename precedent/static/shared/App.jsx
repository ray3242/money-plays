import React, { useEffect, useRef, useState } from 'react';
import { token } from '@atlaskit/tokens';
import { initialize, invoke, isMock, openLink } from './bridge.js';
import './styles.css';

export function Icon({ name = 'arrow', size = 16 }) {
  const paths = { arrow: 'M5 11 11 5M5 5h6v6', plus: 'M8 3v10M3 8h10', check: 'm3 8 3 3 7-7', search: 'M7 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm3-1 3 3', chevron: 'm6 4 4 4-4 4', book: 'M3 2h8a2 2 0 0 1 2 2v10H4a2 2 0 0 1-2-2V3a1 1 0 0 1 1-1Zm-1 9h11', clock: 'M8 4v4l3 2M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Z', close: 'm4 4 8 8M12 4l-8 8', info: 'M8 7v4M8 4v.2M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Z' };
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.arrow} /></svg>;
}
const date = value => value && !Number.isNaN(Date.parse(value)) ? new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(value)) : 'Date unavailable';
const initials = name => name.split(' ').map(part => part[0]).slice(0, 2).join('');
export function SourceLink({ href, children, className = '' }) {
  return <a href={href} className={className} onClick={event => openLink(event, href)}>{children}<Icon /></a>;
}
function Badge({ status }) { return <span className={`badge ${status?.replace(/\s+/g, '-').toLowerCase()}`}>{status}</span>; }
function Empty({ title, children }) { return <div className="empty"><span className="empty-icon"><Icon name="book" size={24} /></span><h3>{title}</h3><p>{children}</p></div>; }
function Loading() { return <div aria-label="Loading evidence" role="status" className="loading"><div className="skeleton short" /><div className="skeleton score-skeleton" />{[1, 2, 3].map(n => <div key={n} className="skeleton row-skeleton" />)}<span className="sr-only">Gathering evidence…</span></div>; }

export function DecisionForm({ issueKey = '', onSaved, onCancel }) {
  const [fields, setFields] = useState({ title: '', decision: '', rationale: '', issueKey });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const titleRef = useRef(null);
  useEffect(() => { titleRef.current?.focus(); }, []);
  const update = event => setFields({ ...fields, [event.target.name]: event.target.value });
  async function submit(event) {
    event.preventDefault();
    const invalid = {};
    for (const [name, max] of [['title', 120], ['decision', 2000], ['rationale', 2000]]) {
      if (!fields[name].trim()) invalid[name] = 'Add this before recording the decision.';
      else if (fields[name].length > max) invalid[name] = `Use ${max} characters or fewer.`;
    }
    if (fields.issueKey && !/^[A-Z][A-Z0-9_]+-\d+$/.test(fields.issueKey)) invalid.issueKey = 'Use an issue key such as PAY-412.';
    setErrors(invalid);
    if (Object.keys(invalid).length) return;
    setBusy(true); setError('');
    try { const entry = await invoke('recordDecision', { ...fields, ...(fields.issueKey ? {} : { issueKey: undefined }) }); onSaved(entry); }
    catch { setError('The decision wasn’t saved. Check your access and try again.'); }
    finally { setBusy(false); }
  }
  return <form className="decision-form" onSubmit={submit} noValidate aria-label="Record a decision">
    <div className="section-heading"><div><span className="eyebrow">CAPTURE THE REASONING</span><h2>Record a decision</h2></div><button className="icon-button" type="button" aria-label="Close decision form" onClick={onCancel}><Icon name="close" /></button></div>
    <p className="muted">What did the team agree to, and why? This will be recorded as accepted.</p>
    {['title', 'decision', 'rationale', 'issueKey'].map(name => <label key={name} className="field" htmlFor={`decision-${name}`}><span>{({ title: 'Title', decision: 'Decision', rationale: 'Rationale', issueKey: 'Linked issue' })[name]} {name === 'issueKey' ? <small>optional</small> : <span className="required">*</span>}</span>
      {['decision', 'rationale'].includes(name) ? <textarea id={`decision-${name}`} name={name} rows={3} value={fields[name]} onChange={update} aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? `${name}-error` : undefined} /> : <input ref={name === 'title' ? titleRef : null} id={`decision-${name}`} name={name} value={fields[name]} onChange={update} readOnly={name === 'issueKey' && Boolean(issueKey)} aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? `${name}-error` : undefined} />}
      {errors[name] && <span className="field-error" id={`${name}-error`}>{errors[name]}</span>}
    </label>)}
    {error && <p role="alert" className="field-error">{error}</p>}
    <div className="form-actions"><span className="muted">Recorded under your account</span><button className="button" type="button" onClick={onCancel}>Cancel</button><button className="button primary" disabled={busy}>{busy ? 'Recording…' : 'Record decision'}</button></div>
  </form>;
}

function Score({ confidence }) {
  const { score, grade, factors } = confidence;
  const tone = grade === 'Ready' ? 'ready' : grade === 'At risk' ? 'at-risk' : 'caution';
  const circumference = 2 * Math.PI * 49;
  return <section aria-label="Ship confidence" className={`confidence ${tone}`}>
    <div className="confidence-top"><div className="ring" role="img" aria-label={`${score} out of 100. ${grade}`}><svg viewBox="0 0 120 120"><circle className="ring-track" cx="60" cy="60" r="49" /><circle className="ring-value" cx="60" cy="60" r="49" style={{ '--circumference': circumference, strokeDasharray: circumference, strokeDashoffset: circumference * (1 - score / 100) }} /></svg><div><strong>{score}</strong><span>/ 100</span></div></div><div className="confidence-copy"><span className="eyebrow">SHIP CONFIDENCE</span><div className="grade-line"><h2>{grade === 'Caution' ? 'A few things to resolve.' : grade === 'Ready' ? 'Evidence points to ready.' : 'Review before shipping.'}</h2><Badge status={grade} /></div><p>Based on linked work and past decisions.<br />A signal for your review, not a release gate.</p></div></div>
    <div className="factor-list">{[...factors].sort((a, b) => a.impact - b.impact).map(factor => <details key={factor.id} className="factor"><summary><span className={factor.impact < 0 ? 'impact negative' : 'impact positive'}>{factor.impact > 0 ? '+' : '−'}{Math.abs(factor.impact)}</span><span>{factor.label}</span><Icon name="chevron" /></summary><div className="factor-evidence"><p>{factor.evidence}</p>{factor.link && <SourceLink href={factor.link}>View supporting issue</SourceLink>}</div></details>)}{!factors.length && <p className="muted">No risk factors found in the available evidence.</p>}</div>
  </section>;
}
function DecisionCard({ entry, selected, onClick }) {
  return <button className={`decision-card ${selected ? 'selected' : ''}`} onClick={onClick} aria-pressed={selected}>
    <div className="card-meta"><Badge status={entry.status} /><span>{entry.issueKey ?? 'Team decision'}</span><span className="card-date">{date(entry.createdAt)}</span></div><h3>{entry.title}</h3><p>{entry.decision}</p><div className="card-bottom"><div className="tags">{entry.tags?.map(tag => <span key={tag}>{tag}</span>)}</div><Icon name="chevron" /></div>
  </button>;
}
function DecisionDetail({ entry, entries, accountId, onUpdated, onSelect, onClose }) {
  const [replacing, setReplacing] = useState(false);
  const [replacement, setReplacement] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const candidates = entries.filter(item => item.id !== entry.id && item.status === 'accepted');
  const canReplace = entry.authorAccountId === accountId && entry.status !== 'superseded';
  async function submit(event) {
    event.preventDefault();
    if (!replacement) return setError('Choose an accepted replacement decision.');
    setBusy(true); setError('');
    try { const updated = await invoke('supersedeDecision', { id: entry.id, byId: replacement }); onUpdated(updated); setReplacing(false); }
    catch { setError('Couldn’t supersede this decision. Only its author can make this change.'); }
    finally { setBusy(false); }
  }
  return <aside className="decision-detail" aria-label="Decision details"><div className="section-heading"><span className="eyebrow">DECISION DETAILS</span>{onClose && <button className="icon-button" onClick={onClose} aria-label="Close decision details"><Icon name="close" /></button>}</div><Badge status={entry.status} /><h2>{entry.title}</h2><div className="detail-author"><span className="avatar small">{entry.authorAccountId === accountId ? 'Y' : 'TM'}</span><span>{entry.authorAccountId === accountId ? 'You' : 'Team member'}<small>Recorded {date(entry.createdAt)}</small></span></div><div className="detail-section"><h3>The decision</h3><p>{entry.decision}</p></div><div className="detail-section"><h3>Why we chose this</h3><p>{entry.rationale || 'No rationale recorded.'}</p></div>{entry.issueKey && <SourceLink href={`/browse/${entry.issueKey}`}>Linked to {entry.issueKey}</SourceLink>}<div className="tags detail-tags">{entry.tags?.map(tag => <span key={tag}>{tag}</span>)}</div>
    {entry.supersededBy && <div className="notice">Replaced by {entries.find(item => item.id === entry.supersededBy) ? <button className="text-button" onClick={() => onSelect(entries.find(item => item.id === entry.supersededBy))}>a newer decision <Icon /></button> : 'another decision. Search the full ledger to find it.'}</div>}
    {canReplace && !replacing && <div className="detail-footer"><button className="button" onClick={() => setReplacing(true)}>Supersede decision</button><p>Keep the history. Link the decision that replaces it.</p></div>}
    {!canReplace && entry.status !== 'superseded' && <p className="muted detail-footer">Only the author can supersede this decision.</p>}
    {replacing && <form className="replace-form" onSubmit={submit}><label className="field">Accepted replacement<select value={replacement} onChange={event => setReplacement(event.target.value)}><option value="">Select a decision</option>{candidates.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>{!candidates.length && <p>No accepted replacements in this view. Record a replacement first.</p>}<p className="muted">The original stays in the ledger as superseded.</p>{error && <p role="alert" className="field-error">{error}</p>}<div className="form-actions"><button className="button" type="button" onClick={() => setReplacing(false)}>Cancel</button><button className="button primary" disabled={busy || !candidates.length}>{busy ? 'Updating…' : 'Confirm replacement'}</button></div></form>}
  </aside>;
}

function Panel({ data, onRecord, accountId, onUpdated }) {
  const [tab, setTab] = useState('Precedents');
  const [selected, setSelected] = useState(null);
  const counts = { Precedents: data.issues.length, Decisions: data.decisions.length, People: data.people.length };
  return <><div className="issue-heading"><span className="issue-key">{data.issue.key}</span><span className="dot" /><span>{data.issue.fields.status?.name ?? 'Issue context'}</span><h1>{data.issue.fields.summary}</h1></div><Score confidence={data.confidence} />
    <div className="tabbar" role="tablist" aria-label="Evidence sections">{Object.keys(counts).map((name, index, names) => <button key={name} role="tab" id={`tab-${name}`} aria-controls="evidence-panel" aria-selected={tab === name} tabIndex={tab === name ? 0 : -1} onClick={() => { setTab(name); setSelected(null); }} onKeyDown={event => { if (['ArrowLeft', 'ArrowRight'].includes(event.key)) { const next = names[(index + (event.key === 'ArrowRight' ? 1 : 2)) % 3]; setTab(next); document.getElementById(`tab-${next}`).focus(); } }} className={tab === name ? 'active' : ''}>{name}<span>{counts[name]}</span></button>)}</div>
    <div role="tabpanel" id="evidence-panel" aria-labelledby={`tab-${tab}`} className="evidence-panel">
    {tab === 'Precedents' && <><div className="section-heading"><div><h2>What happened last time</h2><p>Resolved work with shared context, ranked by keyword overlap.</p></div></div><div className="precedent-list">{data.issues.map((item, index) => <article className="precedent-row" key={item.key}><span className="row-number">{String(index + 1).padStart(2, '0')}</span><div className="precedent-body"><div className="card-meta"><span className="issue-key">{item.key}</span><Badge status={item.kind} /><span className="match">{item.relevance} shared terms</span></div><h3><SourceLink href={item.url}>{item.summary}</SourceLink></h3><span className="muted">Resolved {date(item.resolvedAt)}</span></div></article>)}</div>{!data.issues.length && <Empty title="No close precedents yet">Try adding a more specific summary, labels or components to help connect this work.</Empty>}
    <section className="page-section"><div className="section-heading"><h2>From the decision pages</h2><span className="source-label">CONFLUENCE</span></div>{data.pages.map(page => <article className="page-card" key={page.id}><span className="document-icon"><Icon name="book" size={20} /></span><div><h3><SourceLink href={page.url}>{page.title}</SourceLink></h3><p>{page.excerpt}</p><span className="muted">Updated {date(page.lastModified)}</span></div></article>)}{!data.pages.length && <Empty title="No matching decision pages">No visible Confluence pages matched this issue. Check the warnings below if access is limited.</Empty>}</section></>}
    {tab === 'Decisions' && <><div className="section-heading"><div><h2>The reasoning on record</h2><p>Decisions connected to this issue and its components.</p></div><button className="button compact" onClick={onRecord}><Icon name="plus" />Record</button></div>{data.decisions.map(entry => <DecisionCard key={entry.id} entry={entry} selected={selected?.id === entry.id} onClick={() => setSelected(entry)} />)}{!data.decisions.length && <Empty title="Make the first decision visible">Record what the team agreed to so the next person doesn’t have to ask again.</Empty>}{selected && <DecisionDetail key={selected.id} entry={data.decisions.find(entry => entry.id === selected.id) ?? selected} entries={data.decisions} accountId={accountId} onUpdated={onUpdated} onSelect={setSelected} onClose={() => setSelected(null)} />}</>}
    {tab === 'People' && <><div className="section-heading"><div><h2>People with context</h2><p>Assignees of similar resolved work. A starting point for a conversation.</p></div></div>{data.people.map(person => <div className="person-row" key={person.accountId}><span className="avatar">{initials(person.displayName || 'Team member')}</span><div><h3>{person.displayName || 'Team member'}</h3><div className="person-links">{person.issueKeys.map(key => <SourceLink href={`/browse/${key}`} key={key}>{key}</SourceLink>)}</div></div><span className="muted">{person.count} {person.count === 1 ? 'precedent' : 'precedents'}</span></div>)}{!data.people.length && <Empty title="No context holders found">People will appear here when similar resolved issues have assignees.</Empty>}{Boolean(data.graph?.items?.length) && <section className="page-section"><h2>Related work from Teamwork Graph</h2>{data.graph.items.map(item => <p key={item.id}>{item.title}</p>)}</section>}</>}
    </div>{Boolean(data.warnings?.length) && <details className="warnings"><summary><Icon name="info" />Some context is unavailable <span>{data.warnings.length}</span><Icon name="chevron" /></summary><ul>{data.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul></details>}
    <footer className="panel-footer"><Icon name="check" />Deterministic scoring. Sources you can inspect.</footer></>;
}

export function App({ surface }) {
  const [context, setContext] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(false);
  const [success, setSuccess] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [selected, setSelected] = useState(null);
  const requestId = useRef(0);
  const formRef = useRef(null);
  const isLedger = surface === 'ledger';
  async function load() {
    const current = ++requestId.current;
    setLoading(true); setError('');
    try {
      const ctx = context ?? await initialize();
      const response = await invoke(isLedger ? 'listDecisions' : 'getIssueContext', isLedger ? { query, status: status || undefined } : undefined);
      if (current !== requestId.current) return;
      setContext(ctx); setData(response);
      if (isLedger) setSelected(previous => response.decisions.find(entry => entry.id === previous?.id) ?? response.decisions[0] ?? null);
    } catch { if (current === requestId.current) setError('We couldn’t load the evidence. Check your access to this project and try again.'); }
    finally { if (current === requestId.current) setLoading(false); }
  }
  useEffect(() => { const timer = setTimeout(load, isLedger ? 200 : 0); return () => { clearTimeout(timer); requestId.current++; }; }, [query, status]);
  useEffect(() => { if (form) formRef.current?.scrollIntoView({ block: 'nearest', behavior: 'instant' }); }, [form]);
  function updated(entry) {
    setData(previous => ({ ...previous, decisions: previous.decisions.map(item => item.id === entry.id ? entry : item) }));
    setSelected(entry); setSuccess('Decision superseded. The original reasoning stays on record.');
  }
  async function saved(entry) { setForm(false); setSuccess('Decision recorded. The next person has the context.'); await load(); if (isLedger) setSelected(entry); }
  const entries = data?.decisions ?? [];
  const statuses = ['', 'accepted', 'proposed', 'superseded'];
  return <main className={`app ${isLedger ? 'ledger-app' : 'panel-app'}`} style={{ color: token('color.text', '#172b4d'), background: token('elevation.surface', '#fff') }}><a className="skip-link" href="#content">Skip to content</a>
    <header className="brandbar"><div className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><strong>precedent<span>.</span></strong><span className="brand-divider" /><span className="brand-caption">{isLedger ? 'DECISION LEDGER' : 'BEFORE YOU SHIP'}</span></div>{isMock && <span className="demo-badge">Demo workspace</span>}</header>
    {isLedger && <div className="ledger-heading"><div className="breadcrumb">{context?.extension?.project?.key ?? 'Project'}<span>/</span>Team knowledge</div><div className="ledger-title"><div><h1>Decision ledger</h1><p>The reasoning behind what ships. Kept with the work.</p></div><button className="button primary" onClick={() => { setForm(true); setSuccess(''); }}><Icon name="plus" />Record decision</button></div></div>}
    {!isLedger && <div className="panel-toolbar"><span className="eyebrow">ISSUE CONTEXT</span><button className="text-button" onClick={() => { setForm(true); setSuccess(''); }}><Icon name="plus" />Record decision</button></div>}
    <div id="content" tabIndex={-1}>{success && <div role="status" className="success"><Icon name="check" />{success}<button className="icon-button" aria-label="Dismiss confirmation" onClick={() => setSuccess('')}><Icon name="close" /></button></div>}
    {form && <div ref={formRef}><DecisionForm issueKey={isLedger ? '' : data?.issue?.key} onSaved={saved} onCancel={() => setForm(false)} /></div>}
    {isLedger && <div className="ledger-tools"><div className="search-field"><Icon name="search" /><input aria-label="Search decisions" placeholder="Search decisions, reasoning, or tags…" value={query} onChange={event => setQuery(event.target.value)} />{query && <button className="icon-button" aria-label="Clear search" onClick={() => setQuery('')}><Icon name="close" /></button>}</div><div className="filters" aria-label="Filter by status">{statuses.map(value => <button key={value} className={status === value ? 'active' : ''} aria-pressed={status === value} onClick={() => setStatus(value)}>{value || 'All decisions'}</button>)}</div></div>}
    {error ? <div className="error-state" role="alert"><Icon name="info" size={24} /><h2>Context couldn’t be loaded</h2><p>{error}</p><button className="button primary" onClick={load}>Try again</button></div> : loading ? <Loading /> : data && (isLedger ? <><div className="ledger-count"><span>{entries.length} {entries.length === 1 ? 'decision' : 'decisions'}{query ? ` matching “${query}”` : ' on record'}</span><span><Icon name="clock" />Newest first</span></div>{entries.length ? <div className="ledger-grid"><section className="decision-list" aria-label="Decisions">{entries.map(entry => <DecisionCard key={entry.id} entry={entry} selected={selected?.id === entry.id} onClick={() => setSelected(entry)} />)}<p className="list-footnote">History stays intact. Decisions can be replaced, never erased.</p></section>{selected && <DecisionDetail key={selected.id} entry={entries.find(entry => entry.id === selected.id) ?? selected} entries={entries} accountId={context?.accountId} onUpdated={updated} onSelect={setSelected} />}</div> : <Empty title={query || status ? 'No decisions match this view' : 'Good decisions deserve a record'}>{query || status ? 'Try another search or choose All decisions.' : 'Record your first decision, including the reasoning that led to it.'}</Empty>}</> : <Panel data={data} onRecord={() => setForm(true)} accountId={context?.accountId} onUpdated={updated} />)}
    </div>{isLedger && <footer className="ledger-footer"><span>PRECEDENT</span>Less re-litigating. More shared understanding.</footer>}
  </main>;
}
